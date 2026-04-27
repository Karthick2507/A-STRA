"""ASTRA health check orchestrator - master coordinator of all preflight analysers."""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from playwright.sync_api import sync_playwright

from preflight.anti_bot_analyser import AntiBotAnalyser
from preflight.bearer_token_analyser import BearerTokenAnalyser
from preflight.dom_analyser import DomAnalyser
from preflight.network_interceptor_analyser import NetworkInterceptorAnalyser
from utils.env_loader import ENV
from utils.logger import logger
from utils.report_generator import (
    AnalyserResult,
    PreflightReport,
    build_report,
    generate_reports,
)


def run_health_check() -> PreflightReport:
    """Master orchestrator: runs all 4 preflight analysers."""
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.divider()
    logger.preflight(f"ASTRA Health Check [ID: {run_id}]")
    logger.preflight(f"Environment: {ENV.BASE_URL}")
    logger.divider()

    # Check if we should run health check
    if ENV.HEALTH_CHECK.lower() != "true":
        logger.preflight("Health check disabled (HEALTH_CHECK != true)")
        return PreflightReport(
            run_id=run_id,
            timestamp="",
            overall_status="SKIP",
            total_duration_ms=0,
            environment=ENV.BASE_URL,
            base_url=ENV.BASE_URL,
        )

    analysers: list[AnalyserResult] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=ENV.HEADLESS.lower() == "true")
        context = browser.new_context()
        page = context.new_page()

        try:
            # 1. DOM Analyser
            dom_start = time.time()
            try:
                page.goto(ENV.TARGET_PAGE_URL)
                page.wait_for_load_state("networkidle")
                dom_result = DomAnalyser(page).analyse()
                analysers.append(AnalyserResult(
                    name="DOM Analyser",
                    status="PASS",
                    duration_ms=(time.time() - dom_start) * 1000,
                    findings=dom_result,
                ))
                logger.preflight_result("DOM Analyser", "OK")
            except Exception as exc:
                analysers.append(AnalyserResult(
                    name="DOM Analyser",
                    status="FAIL",
                    duration_ms=(time.time() - dom_start) * 1000,
                    errors=[str(exc)],
                ))
                logger.preflight_result("DOM Analyser", "FAIL", str(exc))

            # 2. Bearer Token Analyser
            token_start = time.time()
            try:
                token_result = BearerTokenAnalyser(page).analyse()
                analysers.append(AnalyserResult(
                    name="Bearer Token Analyser",
                    status="PASS" if token_result["token"] else "SKIP",
                    duration_ms=(time.time() - token_start) * 1000,
                    findings=token_result,
                ))
                logger.preflight_result("Bearer Token Analyser", token_result["status"])
            except Exception as exc:
                analysers.append(AnalyserResult(
                    name="Bearer Token Analyser",
                    status="FAIL",
                    duration_ms=(time.time() - token_start) * 1000,
                    errors=[str(exc)],
                ))
                logger.preflight_result("Bearer Token Analyser", "FAIL", str(exc))

            # 3. Network Interceptor Analyser
            network_start = time.time()
            try:
                network_result = NetworkInterceptorAnalyser(page).analyse()
                analysers.append(AnalyserResult(
                    name="Network Interceptor",
                    status="PASS",
                    duration_ms=(time.time() - network_start) * 1000,
                    findings=network_result,
                ))
                logger.preflight_result("Network Interceptor", "OK")
            except Exception as exc:
                analysers.append(AnalyserResult(
                    name="Network Interceptor",
                    status="FAIL",
                    duration_ms=(time.time() - network_start) * 1000,
                    errors=[str(exc)],
                ))
                logger.preflight_result("Network Interceptor", "FAIL", str(exc))

            # 4. Anti-Bot Analyser
            bot_start = time.time()
            try:
                bot_result = AntiBotAnalyser(page).analyse()
                analysers.append(AnalyserResult(
                    name="Anti-Bot Analyser",
                    status="PASS" if bot_result.is_testable else "WARN",
                    duration_ms=(time.time() - bot_start) * 1000,
                    findings={
                        "threat_level": bot_result.overall_threat_level,
                        "is_testable": bot_result.is_testable,
                        "recommendation": bot_result.recommendation,
                    },
                    warnings=[
                        f"{f.threat_type}: {f.threat_level}" for f in bot_result.findings
                    ],
                ))
                logger.preflight_result("Anti-Bot Analyser", "OK", bot_result.overall_threat_level)
            except Exception as exc:
                analysers.append(AnalyserResult(
                    name="Anti-Bot Analyser",
                    status="FAIL",
                    duration_ms=(time.time() - bot_start) * 1000,
                    errors=[str(exc)],
                ))
                logger.preflight_result("Anti-Bot Analyser", "FAIL", str(exc))

        finally:
            page.close()
            context.close()
            browser.close()

    total_duration = (time.time() - start_time) * 1000

    report = build_report(
        run_id=run_id,
        base_url=ENV.BASE_URL,
        environment="production",
        analysers=analysers,
        total_duration_ms=total_duration,
        metadata={"python_framework": "playwright", "version": "1.0.0"},
    )

    logger.divider()
    logger.preflight(f"Health Check Complete: {report.overall_status}")
    logger.preflight(f"Duration: {total_duration:.0f}ms")
    logger.divider()

    generate_reports(report)
    return report
