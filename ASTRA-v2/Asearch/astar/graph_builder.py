"""
ASTRA-v2 A* Graph Builder.

Generates the set of candidate *successor actions* from a given UI state by
inspecting the live DOM.  Each action represents one edge in the A* graph.

Action types
────────────
    fill(logical_name, value)   — type a value into an input
    click(logical_name)         — click a button / link / checkbox
    select(logical_name, value) — pick an <option>
    navigate(url)               — direct navigation (used at graph root)
    dismiss_popup               — accept/dismiss any active native dialog

Discovery strategy
──────────────────
  1. Query all interactive elements currently visible on the page.
  2. Map them to logical_name if they appear in the registry; otherwise assign
     a synthetic name ("auto.<tag>#<index>").
  3. For inputs with a data context (from Data/UI/*.json), propose fill actions
     with the appropriate test values.
  4. For buttons and links, propose click actions.
  5. Skip disabled, hidden, or already-filled fields.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, TYPE_CHECKING

from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page


# ──────────────────────────────────────────────────────────────────────────────
# Action dataclass
# ──────────────────────────────────────────────────────────────────────────────

class Action:
    """One UI action edge in the A* graph."""
    __slots__ = ("kind", "logical_name", "value", "selector", "cost")

    def __init__(
        self,
        kind:         str,
        logical_name: str,
        selector:     str,
        value:        str = "",
        cost:         float = 1.0,
    ) -> None:
        self.kind         = kind           # fill | click | select | navigate | dismiss_popup
        self.logical_name = logical_name
        self.selector     = selector
        self.value        = value
        self.cost         = cost

    def __repr__(self) -> str:
        if self.value:
            return f"Action({self.kind} {self.logical_name!r} = {self.value!r})"
        return f"Action({self.kind} {self.logical_name!r})"


# ──────────────────────────────────────────────────────────────────────────────
# Graph builder
# ──────────────────────────────────────────────────────────────────────────────

_INTERACTIVE_TAGS = {"input", "button", "select", "textarea", "a"}


class GraphBuilder:
    """Discovers successor actions from the current DOM state."""

    def __init__(
        self,
        data_path: str | Path = "Data/UI",
        registry=None,          # Optional[LocatorRegistry]
    ) -> None:
        self.data_path = Path(data_path)
        self.registry  = registry
        self._data_cache: Dict[str, Any] = {}
        self._load_data_files()

    def _load_data_files(self) -> None:
        if not self.data_path.exists():
            return
        for jf in self.data_path.glob("*.json"):
            try:
                with open(jf, encoding="utf-8") as fh:
                    self._data_cache.update(json.load(fh))
            except Exception as exc:                         # noqa: BLE001
                logger.debug("GraphBuilder: could not load %s — %s", jf, exc)

    def successors(self, page: "Page", already_filled: frozenset) -> List[Action]:
        """Return all currently reachable actions from the DOM."""
        actions: List[Action] = []
        filled_names = {name for name, _ in already_filled}

        try:
            elements = page.query_selector_all(
                "input:not([disabled]):not([type='hidden']), "
                "button:not([disabled]), "
                "select:not([disabled]), "
                "textarea:not([disabled]), "
                "a[href]"
            )
        except Exception as exc:                             # noqa: BLE001
            logger.debug("GraphBuilder.successors DOM query failed: %s", exc)
            return actions

        for idx, el in enumerate(elements):
            try:
                if not el.is_visible():
                    continue
                tag  = (el.evaluate("e => e.tagName.toLowerCase()") or "").lower()
                el_id = el.get_attribute("id") or ""
                name_attr = el.get_attribute("name") or ""
                type_attr = (el.get_attribute("type") or "").lower()
                logical   = self._infer_logical_name(el_id, name_attr, tag, idx)

                if tag == "input" and type_attr not in ("submit", "button", "reset", "image"):
                    if logical in filled_names:
                        continue
                    value = self._lookup_value(logical, type_attr)
                    if value is not None:
                        sel = self._best_selector(el_id, name_attr, tag, idx)
                        actions.append(Action("fill", logical, sel, value=value))

                elif tag == "select":
                    if logical in filled_names:
                        continue
                    option = self._lookup_select_value(logical)
                    if option is not None:
                        sel = self._best_selector(el_id, name_attr, tag, idx)
                        actions.append(Action("select", logical, sel, value=option))

                elif tag in ("button", "a") or type_attr in ("submit", "button"):
                    sel = self._best_selector(el_id, name_attr, tag, idx)
                    text = (el.inner_text() or "").strip()[:50]
                    actions.append(Action("click", logical or text or f"auto.{tag}_{idx}", sel))

            except Exception:                                # noqa: BLE001
                continue

        return actions

    def _infer_logical_name(
        self, el_id: str, name_attr: str, tag: str, idx: int
    ) -> str:
        if el_id:
            return el_id
        if name_attr:
            return name_attr
        return f"auto.{tag}_{idx}"

    def _best_selector(
        self, el_id: str, name_attr: str, tag: str, idx: int
    ) -> str:
        if el_id:
            return f"#{el_id}"
        if name_attr:
            return f"[name='{name_attr}']"
        return f"{tag}:nth-of-type({idx + 1})"

    def _lookup_value(self, logical: str, input_type: str) -> Optional[str]:
        """Return a test value for this field from the data files, or None."""
        if logical in self._data_cache:
            return str(self._data_cache[logical])
        # Type-based defaults for cold-start (no data file)
        defaults = {
            "email":    "test@example.com",
            "password": "Test@1234",
            "text":     "test value",
            "tel":      "0000000000",
            "number":   "1",
            "search":   "test",
        }
        return defaults.get(input_type)

    def _lookup_select_value(self, logical: str) -> Optional[str]:
        if logical in self._data_cache:
            val = self._data_cache[logical]
            if isinstance(val, list) and val:
                return str(val[0])
            return str(val)
        return None
