"""ASTRA Framework - Full pytest/playwright configuration (replaces playwright.config.ts)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

# ── Env defaults (mirrors playwright.config.ts env helpers) ─────────────────
BASE_URL         = os.getenv("BASE_URL", "http://localhost:3000")
HEADLESS        = os.getenv("HEADLESS", "false").lower() != "false"
SLOW_MO         = int(os.getenv("SLOW_MO", "0"))
BROWSER_NAME    = os.getenv("BROWSER", "chromium")          # chromium | firefox | webkit
VIEWPORT_W      = int(os.getenv("VIEWPORT_WIDTH",  "1280"))
VIEWPORT_H      = int(os.getenv("VIEWPORT_HEIGHT", "720"))
ACTION_TIMEOUT  = int(os.getenv("ACTION_TIMEOUT",  "15000"))
NAV_TIMEOUT     = int(os.getenv("NAV_TIMEOUT",     "30000"))
BEARER_TOKEN    = os.getenv("BEARER_TOKEN", "")
TOKEN_TYPE      = os.getenv("TOKEN_TYPE", "Bearer")
REPORT_DIR      = Path(os.getenv("TEST_REPORT_DIR", "reports/testResults"))


# ── Pytest hooks ────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    for marker in [
        "ui: UI browser tests",
        "api: API tests",
        "e2e: End-to-end tests",
        "positive: Positive test cases",
        "negative: Negative test cases",
    ]:
        config.addinivalue_line("markers", marker)


def pytest_runtest_makereport(item, call):
    """Attach screenshots to failed tests (mirrors screenshot: 'only-on-failure')."""
    if call.when == "call" and call.excinfo is not None:
        page: Page | None = item.funcargs.get("page")
        if page:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = item.nodeid.replace("/", "_").replace("::", "__")
            page.screenshot(path=str(REPORT_DIR / f"FAIL_{safe_name}.png"))


# ── Browser launch args (mirrors playwright.config.ts `use` block) ───────────

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    """Headless + slowMo — replaces playwright.config.ts use.headless / use.slowMo."""
    return {
        **browser_type_launch_args,
        "headless": HEADLESS,
        "slow_mo": SLOW_MO,
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """
    Viewport, ignoreHTTPSErrors, extraHTTPHeaders, default timeouts.
    Mirrors playwright.config.ts use.viewport / ignoreHTTPSErrors / extraHTTPHeaders.
    """
    extra_headers = {}
    if BEARER_TOKEN:
        extra_headers["Authorization"] = f"{TOKEN_TYPE} {BEARER_TOKEN}"

    return {
        **browser_context_args,
        "base_url": BASE_URL,
        "viewport": {"width": VIEWPORT_W, "height": VIEWPORT_H},
        "ignore_https_errors": True,
        "extra_http_headers": extra_headers,
    }


@pytest.fixture(scope="session")
def browser_name() -> str:
    """Select browser from BROWSER env var — mirrors playwright.config.ts projects."""
    return BROWSER_NAME


# ── Tracing (mirrors trace: 'on-first-retry') ────────────────────────────────

@pytest.fixture
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Browser context with tracing enabled on retry."""
    ctx = browser.new_context(
        viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
        ignore_https_errors=True,
        extra_http_headers={"Authorization": f"{TOKEN_TYPE} {BEARER_TOKEN}"} if BEARER_TOKEN else {},
        record_video_dir=str(REPORT_DIR / "videos") if os.getenv("RECORD_VIDEO") else None,
    )
    ctx.set_default_timeout(ACTION_TIMEOUT)
    ctx.set_default_navigation_timeout(NAV_TIMEOUT)
    ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield ctx
    # Save trace on failure (mirrors trace: 'on-first-retry')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ctx.tracing.stop(path=str(REPORT_DIR / "trace.zip"))
    ctx.close()


@pytest.fixture
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """Standard page with action + navigation timeouts."""
    p = context.new_page()
    p.set_default_timeout(ACTION_TIMEOUT)
    p.set_default_navigation_timeout(NAV_TIMEOUT)
    yield p
    p.close()


# ── Auth fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_page(page: Page) -> Page:
    """Returns a page already logged in."""
    login_url = os.getenv("LOGIN_URL", f"{BASE_URL}/login")
    username  = os.getenv("APP_USERNAME", "")
    password  = os.getenv("APP_PASSWORD", "")
    page.goto(login_url)
    page.fill("[name=username], [name=email], #username, #email", username)
    page.fill("[name=password], #password", password)
    page.click("[type=submit], button:has-text('Login'), button:has-text('Sign in')")
    page.wait_for_load_state("networkidle")
    return page


@pytest.fixture
def api_headers() -> dict:
    """HTTP headers with Bearer token for API tests."""
    headers = {"Content-Type": "application/json"}
    if BEARER_TOKEN:
        headers["Authorization"] = f"{TOKEN_TYPE} {BEARER_TOKEN}"
    return headers


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL
