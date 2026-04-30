"""
ASTRA-v2 Autopilot — Action Recorder.

Records every UI action taken during an A* run (or manual exploration) as a
structured log.  Used by CodeEmitter to generate Python POM test code.

Each recorded action has:
    kind        fill | click | select | navigate | assert_text | assert_url
    logical_name stable identifier for the element (or URL for navigate)
    selector    raw CSS/ID selector (may be healed later)
    value       string value (fill content / option value / assertion text)
    timestamp   epoch float
    url_before  page URL when the action was initiated
    url_after   page URL after the action completed (may differ for clicks)
    screenshot  optional path to screenshot taken after action (for debug)
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class RecordedAction:
    kind:         str
    logical_name: str
    selector:     str
    value:        str          = ""
    timestamp:    float        = field(default_factory=time.time)
    url_before:   str          = ""
    url_after:    str          = ""
    screenshot:   Optional[str] = None


class ActionRecorder:
    """In-memory list of RecordedActions with JSONL persistence."""

    def __init__(self, session_id: str = "") -> None:
        self.session_id = session_id or f"session_{int(time.time())}"
        self._actions: List[RecordedAction] = []

    def record(
        self,
        kind:         str,
        logical_name: str,
        selector:     str,
        value:        str = "",
        url_before:   str = "",
        url_after:    str = "",
        screenshot:   Optional[str] = None,
    ) -> RecordedAction:
        action = RecordedAction(
            kind=kind,
            logical_name=logical_name,
            selector=selector,
            value=value,
            url_before=url_before,
            url_after=url_after,
            screenshot=screenshot,
        )
        self._actions.append(action)
        return action

    @property
    def actions(self) -> List[RecordedAction]:
        return list(self._actions)

    def save(self, path: str | Path) -> Path:
        """Persist all recorded actions as a JSONL file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            for action in self._actions:
                fh.write(json.dumps(asdict(action)) + "\n")
        return p

    @classmethod
    def load(cls, path: str | Path) -> "ActionRecorder":
        recorder = cls()
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    recorder._actions.append(RecordedAction(**data))
        return recorder

    def clear(self) -> None:
        self._actions.clear()

    def __len__(self) -> int:
        return len(self._actions)
