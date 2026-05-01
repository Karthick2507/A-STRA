"""
ASTRA-v2 Autopilot Runner.

Ties together the A* engine, action recorder, and code emitter into a single
entry point.  The runner:

    1. Launches a Playwright page (or accepts an existing one)
    2. Runs A* from `start_url` toward `goal`
    3. Replays the discovered path, recording every action via ActionRecorder
    4. Emits a Python pytest file for the discovered path
    5. Optionally writes a JSONL action log for later inspection

Usage
─────
    runner = AutopilotRunner(
        page=page,
        goal=GoalSpec(url_patterns=["**/dashboard**"], text_patterns=["Welcome"]),
        start_url="https://app.example.com/login",
        output_dir="Asearch/autopilot/sessions",
    )
    result = runner.run()
    # result.test_file  → path to generated pytest file
    # result.astar      → AStarResult
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from core.logging import logger
from core.config.config_loader import CONFIG
from Asearch.astar.engine import AStarEngine, AStarResult
from Asearch.astar.heuristic import GoalSpec
from Asearch.astar.graph_builder import Action
from Asearch.autopilot.action_recorder import ActionRecorder, RecordedAction
from Asearch.autopilot.code_emitter import CodeEmitter

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Asearch.self_healing.healer import HealerOrchestrator


@dataclass
class AutopilotRunResult:
    success:    bool
    astar:      AStarResult
    test_file:  Optional[Path] = None
    log_file:   Optional[Path] = None
    session_id: str = ""


class AutopilotRunner:
    """Run A* autopilot and emit a pytest test for the discovered path."""

    def __init__(
        self,
        page:        "Page",
        goal:        GoalSpec,
        start_url:   Optional[str] = None,
        output_dir:  str | Path = "Asearch/autopilot/sessions",
        page_class:  str = "BasePage",
        page_import: str = "from UI.pages.base_page import BasePage",
        healer:      Optional["HealerOrchestrator"] = None,
        data_path:   str = "Data/UI",
    ) -> None:
        self.page        = page
        self.goal        = goal
        self.start_url   = start_url
        self.output_dir  = Path(output_dir)
        self.page_class  = page_class
        self.page_import = page_import
        self.healer      = healer
        self.session_id  = f"ap_{int(time.time())}"
        self._engine     = AStarEngine(
            page=page,
            goal=goal,
            healer=healer,
            data_path=data_path,
        )
        self._recorder   = ActionRecorder(self.session_id)

    def run(self) -> AutopilotRunResult:
        logger.autopilot(
            "AutopilotRunner starting session %s → goal=%s",
            self.session_id, self.goal.url_patterns,
        )

        astar_result = self._engine.search(start_url=self.start_url)

        if not astar_result.success:
            logger.autopilot(
                "A* search failed: %s — no test file generated", astar_result.reason
            )
            return AutopilotRunResult(
                success=False,
                astar=astar_result,
                session_id=self.session_id,
            )

        # Replay path through the recorder so we capture typed values
        self._record_path(astar_result.path)

        # Persist action log
        self.output_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._recorder.save(self.output_dir / f"{self.session_id}.jsonl")

        # Emit test code
        emitter = CodeEmitter(
            session_id=self.session_id,
            page_class=self.page_class,
            page_import=self.page_import,
            goal_text=self.goal.text_patterns[0] if self.goal.text_patterns else None,
            goal_selector=self.goal.element_selectors[0] if self.goal.element_selectors else None,
        )
        test_file = emitter.save(
            self._recorder.actions,
            self.output_dir / f"test_{self.session_id}.py",
        )

        logger.autopilot(
            "Autopilot session %s complete — %d actions → %s",
            self.session_id, len(self._recorder), test_file,
        )
        return AutopilotRunResult(
            success=True,
            astar=astar_result,
            test_file=test_file,
            log_file=log_file,
            session_id=self.session_id,
        )

    def _record_path(self, path_descriptions: list[str]) -> None:
        """Parse the A* path description strings back into RecordedActions."""
        import re
        url = self.start_url or self.page.url

        for desc in path_descriptions:
            # fill("logical_name", "value")
            m = re.match(r"fill\('(.+?)', '(.+?)'\)", desc)
            if m:
                self._recorder.record("fill", m.group(1), "", m.group(2), url_before=url)
                continue

            # click("logical_name")
            m = re.match(r"click\('(.+?)'\)", desc)
            if m:
                self._recorder.record("click", m.group(1), "", url_before=url)
                url = self.page.url
                continue

            # select("logical_name", "value")
            m = re.match(r"select\('(.+?)', '(.+?)'\)", desc)
            if m:
                self._recorder.record("select", m.group(1), "", m.group(2), url_before=url)
                continue

            # navigate("url")
            m = re.match(r"navigate\('(.+?)'\)", desc)
            if m:
                nav_url = m.group(1)
                self._recorder.record("navigate", nav_url, nav_url, nav_url, url_before=url)
                url = nav_url
                continue
