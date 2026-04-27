"""ASTRA UI test runner - orchestrates UI schema → reconciliation → code gen → execution."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright
from utils.env_loader import ENV
from utils.logger import logger
from utils.schema_resolver import load_ui_schema
from utils.schema_reconciler import reconcile_ui_schema
from core.search.a_star_engine import AStarEngine
from codegen.ui_code_generator import UiCodeGenerator


class UiTestRunner:
    def __init__(
        self,
        skip_preflight: bool = False,
        skip_schema_gen: bool = False,
    ) -> None:
        self.skip_preflight = skip_preflight
        self.skip_schema_gen = skip_schema_gen

    def run(self) -> None:
        logger.divider()
        logger.preflight("UI Test Runner")
        logger.divider()

        # 1. Load schema
        logger.preflight("[1/5] Loading UI schema...")
        schema = load_ui_schema()

        # 2. Reconcile schema with live DOM (self-healing)
        logger.preflight("[2/5] Reconciling schema with live DOM...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=ENV.HEADLESS.lower() == "true")
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(schema.target_endpoint)
                page.wait_for_load_state("networkidle")
                reconciled_schema, report = reconcile_ui_schema(page, schema)
                logger.preflight(
                    f"  Reconciled: +{len(report.added_fields)} "
                    f"-{len(report.removed_fields)} ~{len(report.updated_fields)}"
                )
            finally:
                page.close()
                context.close()
                browser.close()

        # 3. Run A* search
        logger.preflight("[3/5] Running A* search...")
        engine = AStarEngine(reconciled_schema)
        result = engine.search()
        logger.preflight(engine.get_search_summary(result))

        # 4. Generate tests
        if not self.skip_schema_gen:
            logger.preflight("[4/5] Generating UI tests...")
            generator = UiCodeGenerator(reconciled_schema, result)
            files = generator.generate()
            logger.preflight(f"  Generated {len(files)} test files")
        else:
            logger.preflight("[4/5] Skipping code generation")

        # 5. Execute tests
        logger.preflight("[5/5] Running tests...")
        self._run_pytest()
        logger.divider()

    def _run_pytest(self) -> None:
        try:
            result = subprocess.run(
                ["pytest", "tests/ui", "-v", "--tb=short"],
                capture_output=False,
            )
            if result.returncode != 0:
                logger.warning(f"Some tests failed (exit code {result.returncode})")
        except FileNotFoundError:
            logger.warning("pytest not found. Install with: pip install pytest")
