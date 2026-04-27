"""ASTRA Framework - Pytest configuration and shared fixtures."""
from __future__ import annotations

import os
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from utils.env_loader import ENV


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "ui: UI browser tests")
    config.addinivalue_line("markers", "api: API tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "positive: Positive test cases")
    config.addinivalue_line("markers", "negative: Negative test cases")


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {
        "headless": ENV.HEADLESS.lower() == "true",
        "slow_mo": 100,
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "base_url": ENV.BASE_URL,
    }


@pytest.fixture(scope="session")
def base_url():
    return ENV.BASE_URL


@pytest.fixture
def authenticated_page(page: Page) -> Page:
    """Returns a page already logged in."""
    page.goto(ENV.LOGIN_URL)
    page.fill("[name=username], [name=email], #username, #email", ENV.APP_USERNAME)
    page.fill("[name=password], #password", ENV.APP_PASSWORD)
    page.click("[type=submit], button:has-text('Login'), button:has-text('Sign in')")
    page.wait_for_load_state("networkidle")
    return page


@pytest.fixture
def api_headers():
    """Returns HTTP headers with Bearer token for API tests."""
    headers = {"Content-Type": "application/json"}
    if ENV.BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {ENV.BEARER_TOKEN}"
    return headers
