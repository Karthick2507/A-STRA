"""
PRISM MenuPage POM.

Represents the application's main navigation menu after login.
Demonstrates multi-element registration and nested navigation patterns.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from UI.pages.base_page import BasePage
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page


class MenuPage(BasePage):
    """Page Object for the main navigation menu / sidebar."""

    _LOCATORS = {
        "menu.container": (
            "nav[aria-label='Main navigation']",
            "aria",
            {"tag": "nav", "aria-label": "Main navigation"},
        ),
        "menu.dashboard": (
            "a[href='/dashboard']",
            "css",
            {"tag": "a", "text": "Dashboard", "href": "/dashboard"},
            {"parent_selector": "nav", "nth": 0},
        ),
        "menu.reports": (
            "a[href='/reports']",
            "css",
            {"tag": "a", "text": "Reports", "href": "/reports"},
            {"parent_selector": "nav", "nth": 1},
        ),
        "menu.settings": (
            "a[href='/settings']",
            "css",
            {"tag": "a", "text": "Settings", "href": "/settings"},
            {"parent_selector": "nav"},
        ),
        "menu.user_profile": (
            "#user-profile-btn",
            "id",
            {"id": "user-profile-btn", "tag": "button", "aria-label": "User profile"},
        ),
        "menu.logout": (
            "#logout-btn",
            "id",
            {"id": "logout-btn", "tag": "button", "text": "Logout"},
        ),
        "menu.search": (
            "input[placeholder='Search…']",
            "css",
            {"tag": "input", "placeholder": "Search…"},
        ),
    }

    def __init__(self, page: "Page") -> None:
        super().__init__(page)

    # ------------------------------------------------------------------
    # Page actions
    # ------------------------------------------------------------------

    def go_to_dashboard(self) -> None:
        self.click("menu.dashboard")
        self.page.wait_for_url("**/dashboard**", timeout=10_000)
        logger.info("Navigated to Dashboard")

    def go_to_reports(self) -> None:
        self.click("menu.reports")
        self.page.wait_for_url("**/reports**", timeout=10_000)
        logger.info("Navigated to Reports")

    def go_to_settings(self) -> None:
        self.click("menu.settings")
        self.page.wait_for_url("**/settings**", timeout=10_000)
        logger.info("Navigated to Settings")

    def logout(self) -> None:
        self.click("menu.logout")
        logger.info("Logged out")

    def search(self, query: str) -> None:
        self.fill("menu.search", query)
        self.page.keyboard.press("Enter")

    def is_nav_visible(self) -> bool:
        return self.is_visible("menu.container")

    def get_active_item(self) -> Optional[str]:
        """Return text of the currently highlighted nav item, or None."""
        try:
            active = self.page.query_selector("nav .active, nav [aria-current='page']")
            return active.inner_text() if active else None
        except Exception:                                     # noqa: BLE001
            return None
