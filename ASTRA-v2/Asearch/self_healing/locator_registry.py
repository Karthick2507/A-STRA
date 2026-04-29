"""
ASTRA-v2 Locator Registry (SQLite-backed).

Schema:

    locator_records
    ┌────────────────────┬──────────────────────────────────────────────────┐
    │ logical_name       │ The stable test-side identifier (e.g. 'login.email') │
    │ page_url           │ URL where this locator was last observed         │
    │ selector           │ Live Playwright selector ('#email')              │
    │ selector_kind      │ id | name | aria | css | xpath | text            │
    │ attributes_json    │ JSON snapshot of element attributes (id/class/aria/text…) │
    │ neighbours_json    │ JSON snapshot of parent + sibling tag/text/index │
    │ created_at         │ First time this variant was seen / saved         │
    │ last_used_at       │ Last successful resolution                       │
    │ success_count      │ # times this variant resolved successfully       │
    │ heal_source        │ NULL | 'id' | 'name' | 'aria' | 'class' | 'dom' | 'registry' | 'ml' │
    │ confidence         │ 0..1 ML/heuristic score that produced this entry │
    │ active             │ 1 if currently the canonical pick for logical_name │
    └────────────────────┴──────────────────────────────────────────────────┘

Each `logical_name` may have multiple historical variants — the one with active=1
is the current canonical. When healing succeeds, the old variant is marked
active=0 and a new row is inserted with active=1.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logging import logger


@dataclass
class LocatorRecord:
    logical_name:    str
    page_url:        str
    selector:        str
    selector_kind:   str                                # id | name | aria | css | xpath | text
    attributes:      Dict[str, Any] = field(default_factory=dict)
    neighbours:      Dict[str, Any] = field(default_factory=dict)
    created_at:      float          = 0.0
    last_used_at:    float          = 0.0
    success_count:   int            = 0
    heal_source:     Optional[str]  = None              # 'id' | 'aria' | … | 'ml' | None for human-defined
    confidence:      float          = 1.0
    active:          bool           = True
    id:              Optional[int]  = None              # SQLite rowid

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "LocatorRecord":
        return cls(
            id            = row["id"],
            logical_name  = row["logical_name"],
            page_url      = row["page_url"],
            selector      = row["selector"],
            selector_kind = row["selector_kind"],
            attributes    = json.loads(row["attributes_json"] or "{}"),
            neighbours    = json.loads(row["neighbours_json"] or "{}"),
            created_at    = row["created_at"],
            last_used_at  = row["last_used_at"],
            success_count = row["success_count"],
            heal_source   = row["heal_source"],
            confidence    = row["confidence"],
            active        = bool(row["active"]),
        )


class LocatorRegistry:
    """Thread-safe SQLite-backed locator history.

    Usage:
        reg = LocatorRegistry("Data/locators/locator_registry.db")
        reg.upsert_initial("login.email", "https://app/login", "#email", "id", {"id": "email"})
        record = reg.get_active("login.email")
        reg.record_success(record.id)
        reg.replace_with_healed(old_id=record.id, new_record=...)
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS locator_records (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        logical_name    TEXT    NOT NULL,
        page_url        TEXT    NOT NULL,
        selector        TEXT    NOT NULL,
        selector_kind   TEXT    NOT NULL,
        attributes_json TEXT    NOT NULL DEFAULT '{}',
        neighbours_json TEXT    NOT NULL DEFAULT '{}',
        created_at      REAL    NOT NULL,
        last_used_at    REAL    NOT NULL,
        success_count   INTEGER NOT NULL DEFAULT 0,
        heal_source     TEXT,
        confidence      REAL    NOT NULL DEFAULT 1.0,
        active          INTEGER NOT NULL DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_logical_active
        ON locator_records (logical_name, active);

    CREATE INDEX IF NOT EXISTS idx_logical_url
        ON locator_records (logical_name, page_url);
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()
        logger.debug("LocatorRegistry initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(self._SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def upsert_initial(
        self,
        logical_name: str,
        page_url:     str,
        selector:     str,
        selector_kind: str,
        attributes:   Optional[Dict[str, Any]] = None,
        neighbours:   Optional[Dict[str, Any]] = None,
    ) -> LocatorRecord:
        """Insert a human-defined locator if not already present.

        Idempotent: if a row with the same logical_name + selector already exists,
        do nothing and return it.
        """
        now = time.time()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM locator_records "
                "WHERE logical_name = ? AND selector = ? "
                "ORDER BY id DESC LIMIT 1",
                (logical_name, selector),
            ).fetchone()
            if row is not None:
                return LocatorRecord.from_row(row)

            cur = conn.execute(
                "INSERT INTO locator_records "
                "(logical_name, page_url, selector, selector_kind, "
                " attributes_json, neighbours_json, "
                " created_at, last_used_at, success_count, heal_source, confidence, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 1.0, 1)",
                (
                    logical_name, page_url, selector, selector_kind,
                    json.dumps(attributes or {}),
                    json.dumps(neighbours or {}),
                    now, now,
                ),
            )
            new_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM locator_records WHERE id = ?", (new_id,)
            ).fetchone()
            return LocatorRecord.from_row(row)

    def get_active(self, logical_name: str) -> Optional[LocatorRecord]:
        """Return the currently active locator for a logical name (or None)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM locator_records "
                "WHERE logical_name = ? AND active = 1 "
                "ORDER BY id DESC LIMIT 1",
                (logical_name,),
            ).fetchone()
            return LocatorRecord.from_row(row) if row else None

    def get_history(self, logical_name: str, limit: int = 25) -> List[LocatorRecord]:
        """Return historical variants for a logical name, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM locator_records "
                "WHERE logical_name = ? "
                "ORDER BY id DESC LIMIT ?",
                (logical_name, limit),
            ).fetchall()
            return [LocatorRecord.from_row(r) for r in rows]

    def record_success(self, record_id: int) -> None:
        """Mark a locator as having resolved successfully."""
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE locator_records "
                "SET success_count = success_count + 1, last_used_at = ? "
                "WHERE id = ?",
                (now, record_id),
            )

    def replace_with_healed(
        self,
        logical_name: str,
        new_selector:  str,
        new_kind:      str,
        heal_source:   str,
        confidence:    float,
        page_url:      str,
        attributes:    Optional[Dict[str, Any]] = None,
        neighbours:    Optional[Dict[str, Any]] = None,
    ) -> LocatorRecord:
        """Deactivate all current variants and insert a new active row.

        Returns the newly active record.
        """
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE locator_records SET active = 0 WHERE logical_name = ?",
                (logical_name,),
            )
            cur = conn.execute(
                "INSERT INTO locator_records "
                "(logical_name, page_url, selector, selector_kind, "
                " attributes_json, neighbours_json, "
                " created_at, last_used_at, success_count, heal_source, confidence, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1)",
                (
                    logical_name, page_url, new_selector, new_kind,
                    json.dumps(attributes or {}),
                    json.dumps(neighbours or {}),
                    now, now,
                    heal_source, confidence,
                ),
            )
            row = conn.execute(
                "SELECT * FROM locator_records WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            healed = LocatorRecord.from_row(row)
            logger.heal(
                "Healed locator %r → %s (%s, conf=%.2f, source=%s)",
                logical_name, new_selector, new_kind, confidence, heal_source,
            )
            return healed

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def export_json(self, target: str | Path) -> Path:
        """Export the entire registry to a JSON file (for backup/diff)."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM locator_records ORDER BY logical_name, id"
            ).fetchall()
            payload = [asdict(LocatorRecord.from_row(r)) for r in rows]
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Exported %d locator records → %s", len(payload), target)
        return target

    def stats(self) -> Dict[str, int]:
        """Return basic counts (used in reports)."""
        with self._connect() as conn:
            total       = conn.execute("SELECT COUNT(*) FROM locator_records").fetchone()[0]
            active      = conn.execute("SELECT COUNT(*) FROM locator_records WHERE active=1").fetchone()[0]
            healed      = conn.execute("SELECT COUNT(*) FROM locator_records WHERE heal_source IS NOT NULL").fetchone()[0]
            distinct    = conn.execute("SELECT COUNT(DISTINCT logical_name) FROM locator_records").fetchone()[0]
            return {
                "total_records":      total,
                "active_records":     active,
                "healed_records":     healed,
                "distinct_logicals":  distinct,
            }
