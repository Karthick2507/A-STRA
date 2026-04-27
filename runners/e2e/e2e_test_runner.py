"""ASTRA E2E test runner - full 5-phase pipeline."""
from __future__ import annotations

import subprocess
import time
import uuid
from typing import Optional

from utils.env_loader import ENV
from utils.logger import logger
from preflight.health_check_orchestrator import run_health_check
from core.schema_builder import build_schemas_from_preflight
from runners.ui.ui_test_runner import UiTestRunner
from runners.api.api_test_runner import ApiTestRunner
from utils.report_generator import generate_reports, build_report, AnalyserResult


class E2ETestRunner:
    def __init__(
        self,
        skip_preflight: bool = False,
        skip_ui: bool = False,
        skip_api: bool = False,
        skip_schema_gen: bool = False,
    ) -> None:
        self.skip_preflight = skip_preflight
        self.skip_ui = skip_ui
        self.skip_api = skip_api
        self.skip_schema_gen = skip_schema_gen
        self.run_id = str(uuid.uuid4())[:8]

    def run(self) -> None:
        logger.divider()
        logger.preflight(f"E2E Test Pipeline [ID: {self.run_id}]")
        logger.divider()
        start_time = time.time()

        try:
            # Phase 1: Preflight
            if not self.skip_preflight:
                logger.preflight("\n[PHASE 1/5] Preflight Health Checks")
                preflight_report = run_health_check()
                if preflight_report.overall_status == "FAIL":
                    logger.warning("Preflight failed. Aborting E2E.")
                    return
            else:
                logger.preflight("\n[PHASE 1/5] Skipping preflight")
                preflight_report = None

            # Phase 2: Schema Build
            logger.preflight("\n[PHASE 2/5] Building Schemas from Preflight")
            dom_findings = None
            network_findings = None
            if preflight_report:
                for analyser in preflight_report.analysers:
                    if analyser.name == "DOM Analyser":
                        dom_findings = analyser.findings
                    elif analyser.name == "Network Interceptor":
                        network_findings = analyser.findings
            schemas = build_schemas_from_preflight(dom_findings, network_findings)
            logger.preflight(f"  Built {len(schemas)} schemas")

            # Phase 3: UI Tests
            if not self.skip_ui:
                logger.preflight("\n[PHASE 3/5] Running UI Tests")
                ui_runner = UiTestRunner(skip_schema_gen=self.skip_schema_gen)
                ui_runner.run()
            else:
                logger.preflight("\n[PHASE 3/5] Skipping UI tests")

            # Phase 4: API Tests
            if not self.skip_api:
                logger.preflight("\n[PHASE 4/5] Running API Tests")
                api_runner = ApiTestRunner(skip_schema_gen=self.skip_schema_gen)
                api_runner.run()
            else:
                logger.preflight("\n[PHASE 4/5] Skipping API tests")

            # Phase 5: Report
            duration_ms = (time.time() - start_time) * 1000
            logger.preflight("\n[PHASE 5/5] Generating E2E Report")
            logger.preflight(f"E2E Complete in {duration_ms:.0f}ms")

        except Exception as exc:
            logger.error(f"E2E pipeline failed: {exc}")
            raise
        finally:
            logger.divider()
