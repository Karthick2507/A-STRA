"""
ASTRA-v2 Autopilot — Code Emitter.

Converts a sequence of RecordedActions into a valid Python pytest test file
following the ASTRA-v2 POM style.

Generated test structure
────────────────────────
    from UI.pages.xxx_page import XxxPage
    import pytest

    def test_autopilot_<session_id>(page):
        # ── setup
        p = XxxPage(page)
        p.navigate("<start_url>")

        # ── actions
        p.fill("login.email", "user@example.com")
        p.click("login.submit")

        # ── assertions (inserted at URL change + goal detection points)
        assert "dashboard" in page.url
        assert page.locator("text=Welcome").is_visible()

Assertion injection rules
─────────────────────────
  1. After every navigate/click that changes the URL → assert URL fragment
  2. After the final action → assert goal text / element if configured
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import List, Optional

from Asearch.autopilot.action_recorder import RecordedAction


class CodeEmitter:
    """Emit a pytest test function from recorded autopilot actions."""

    def __init__(
        self,
        session_id:    str = "autopilot",
        page_class:    str = "BasePage",
        page_import:   str = "from UI.pages.base_page import BasePage",
        goal_text:     Optional[str] = None,
        goal_selector: Optional[str] = None,
    ) -> None:
        self.session_id    = _sanitise_id(session_id)
        self.page_class    = page_class
        self.page_import   = page_import
        self.goal_text     = goal_text
        self.goal_selector = goal_selector

    def emit(self, actions: List[RecordedAction]) -> str:
        """Return the complete test file as a string."""
        lines: List[str] = []

        # Imports
        lines += [
            self.page_import,
            "import pytest",
            "",
            "",
            f"def test_autopilot_{self.session_id}(page):",
        ]

        if not actions:
            lines.append('    pass  # no actions recorded')
            return "\n".join(lines) + "\n"

        # Find start URL
        start_url = actions[0].url_before or actions[0].url_after or ""
        if start_url:
            lines.append(f"    pom = {self.page_class}(page)")
            lines.append(f'    pom.navigate("{start_url}")')
        else:
            lines.append(f"    pom = {self.page_class}(page)")
        lines.append("")

        prev_url = start_url
        for action in actions:
            line = self._emit_action(action)
            if line:
                lines.append(f"    {line}")
            # URL-change assertion
            if action.url_after and action.url_after != prev_url:
                fragment = _url_fragment(action.url_after)
                if fragment:
                    lines.append(f'    assert "{fragment}" in page.url')
                prev_url = action.url_after

        # Goal assertions
        lines.append("")
        if self.goal_text:
            lines.append(f'    assert page.locator("text={self.goal_text}").is_visible()')
        if self.goal_selector:
            lines.append(f'    assert page.locator("{self.goal_selector}").is_visible()')

        return "\n".join(lines) + "\n"

    def save(self, actions: List[RecordedAction], path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.emit(actions), encoding="utf-8")
        return p

    # ------------------------------------------------------------------
    # Per-action line generation
    # ------------------------------------------------------------------

    def _emit_action(self, a: RecordedAction) -> str:
        if a.kind == "fill":
            return f'pom.fill("{a.logical_name}", {a.value!r})'
        if a.kind == "click":
            return f'pom.click("{a.logical_name}")'
        if a.kind == "select":
            return f'pom.select("{a.logical_name}", {a.value!r})'
        if a.kind == "navigate":
            return f'pom.navigate("{a.value}")'
        if a.kind == "assert_text":
            return f'assert pom.get_text("{a.logical_name}") == {a.value!r}'
        if a.kind == "assert_url":
            return f'assert "{a.value}" in page.url'
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sanitise_id(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", s).strip("_") or "run"


def _url_fragment(url: str) -> str:
    """Extract the first meaningful path segment for assertion."""
    path = url.split("?")[0].split("#")[0]
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else ""
