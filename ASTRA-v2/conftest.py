"""
ASTRA-v2 root conftest.py.

Provides pytest fixtures shared across all tests:
  - browser / page (Playwright, per-test context)
  - api_client (APIClient session-scoped, auth from config)
  - allure failure hooks (screenshot + trace on test failure)
  - run_report accumulator + post-run notify_all call
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from core.config import CONFIG
from core.logging import logger
from core.reporting.allure_helper import attach_screenshot, attach_trace
from core.reporting.notifiers import RunReport, notify_all


# ──────────────────────────────────────────────────────────────────────────────
# Session-level counters for notify_all
# ──────────────────────────────────────────────────────────────────────────────

_run_stats = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "start": 0.0, "failures": []}


def pytest_sessionstart(session) -> None:
    _run_stats["start"] = time.time()


def pytest_runtest_logreport(report) -> None:
    if report.when != "call":
        return
    _run_stats["total"] += 1
    if report.passed:
        _run_stats["passed"] += 1
    elif report.failed:
        _run_stats["failed"] += 1
        _run_stats["failures"].append(report.nodeid)
    elif report.skipped:
        _run_stats["skipped"] += 1


def pytest_sessionfinish(session, exitstatus) -> None:
    elapsed = time.time() - _run_stats["start"]
    env = CONFIG.default_env
    branch = os.getenv("GIT_BRANCH", os.getenv("BRANCH_NAME", ""))
    job_url = os.getenv("BUILD_URL", "")

    report = RunReport(
        total=_run_stats["total"],
        passed=_run_stats["passed"],
        failed=_run_stats["failed"],
        skipped=_run_stats["skipped"],
        duration=elapsed,
        env=env,
        branch=branch,
        job_url=job_url,
        failures=_run_stats["failures"][:5],
    )
    logger.info(
        "Run complete: %d total, %d passed, %d failed, %.1fs",
        report.total, report.passed, report.failed, elapsed,
    )
    notify_all(report)


# ──────────────────────────────────────────────────────────────────────────────
# Playwright browser fixture
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_type_launch_args():
    browser_cfg = CONFIG.browser
    return {
        "headless": browser_cfg.get("headless", True),
        "slow_mo":  browser_cfg.get("slow_mo_ms", 0),
        "args":     ["--no-sandbox", "--disable-dev-shm-usage"],
    }


@pytest.fixture(scope="function")
def browser_context_args(tmp_path):
    browser_cfg = CONFIG.browser
    vp = browser_cfg.get("viewport", {"width": 1280, "height": 720})
    opts = {
        "viewport": vp,
        "record_video_dir": str(tmp_path / "videos") if browser_cfg.get("video", False) else None,
    }
    if browser_cfg.get("trace", False):
        opts["record_trace"] = True
    return {k: v for k, v in opts.items() if v is not None}


@pytest.fixture(scope="function")
def page(browser: Browser, browser_context_args: dict, request) -> Generator[Page, None, None]:
    context: BrowserContext = browser.new_context(**browser_context_args)

    # Start tracing if configured
    trace_enabled = CONFIG.browser.get("trace", False)
    if trace_enabled:
        context.tracing.start(screenshots=True, snapshots=True)

    pg: Page = context.new_page()
    pg.set_default_timeout(CONFIG.browser.get("timeout_ms", 30_000))
    pg.set_default_navigation_timeout(CONFIG.browser.get("navigation_timeout_ms", 30_000))

    yield pg

    # On failure — attach screenshot + trace to Allure
    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        attach_screenshot(pg, name="failure-screenshot")
        if trace_enabled:
            trace_path = str(Path("Data/traces") / f"{request.node.name}.zip")
            Path("Data/traces").mkdir(parents=True, exist_ok=True)
            context.tracing.stop(path=trace_path)
            attach_trace(trace_path)
    else:
        if trace_enabled:
            context.tracing.stop()

    context.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ──────────────────────────────────────────────────────────────────────────────
# API client fixture
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def api_client():
    """Session-scoped APIClient using Bearer token from environment / config."""
    from API.client import APIClient, BearerAuth
    env_cfg = CONFIG.environments.get(CONFIG.default_env, {})
    api_url = env_cfg.get("api_url", "")
    token   = os.getenv("API_TOKEN", "")
    auth    = BearerAuth(token) if token else None
    client  = APIClient(api_url, auth=auth)
    yield client
    # No explicit close needed (context-manager pattern used per-test)
