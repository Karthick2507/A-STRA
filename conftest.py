"""
PRISM root conftest.py.

Minimal pytest fixtures for shadow_coding + self_healing development.
Plugin consumers bring their own fixtures.
"""
from __future__ import annotations

from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from core.config import CONFIG


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {
        "headless": CONFIG.headless,
        "slow_mo":  CONFIG.slow_mo_ms,
        "args":     ["--no-sandbox", "--disable-dev-shm-usage"],
    }


@pytest.fixture(scope="function")
def browser_context_args():
    return {"viewport": CONFIG.viewport}


@pytest.fixture(scope="function")
def page(browser: Browser, browser_context_args: dict) -> Generator[Page, None, None]:
    context: BrowserContext = browser.new_context(**browser_context_args)
    pg: Page = context.new_page()
    pg.set_default_timeout(CONFIG.action_timeout_ms)
    pg.set_default_navigation_timeout(CONFIG.navigation_timeout_ms)
    yield pg
    context.close()
