"""ASTRA API test runner - orchestrates API schema → code gen → execution."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from utils.env_loader import ENV
from utils.logger import logger
from utils.schema_resolver import load_api_schema
from utils.schema_reconciler import reconcile_api_schema
from core.search.a_star_engine import AStarEngine
from codegen.api_code_generator import ApiCodeGenerator


class ApiTestRunner:
    def __init__(
        self,
        skip_preflight: bool = False,
        skip_schema_gen: bool = False,
    ) -> None:
        self.skip_preflight = skip_preflight
        self.skip_schema_gen = skip_schema_gen

    def run(self) -> None:
        logger.divider()
        logger.preflight("API Test Runner")
        logger.divider()

        # 1. Load schema
        logger.preflight("[1/5] Loading API schema...")
        schema = load_api_schema()

        # 2. Reconcile (optional, mostly for UI)
        logger.preflight("[2/5] Reconciling schema...")
        reconciled_schema, report = reconcile_api_schema(schema)

        # 3. Run A* search
        logger.preflight("[3/5] Running A* search...")
        engine = AStarEngine(reconciled_schema)
        result = engine.search()
        logger.preflight(engine.get_search_summary(result))

        # 4. Generate tests
        if not self.skip_schema_gen:
            logger.preflight("[4/5] Generating API tests...")
            generator = ApiCodeGenerator(reconciled_schema, result, {})
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
                ["pytest", "tests/api", "-v", "--tb=short"],
                capture_output=False,
            )
            if result.returncode != 0:
                logger.warning(f"Some tests failed (exit code {result.returncode})")
        except FileNotFoundError:
            logger.warning("pytest not found. Install with: pip install pytest")
