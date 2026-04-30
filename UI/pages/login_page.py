"""
ASTRA-v2 LoginPage POM.

Demonstrates the BasePage pattern: declare _LOCATORS once, then use
logical names throughout all test methods.  Self-healing is automatic —
no test code needs to change when a selector breaks.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from UI.pages.base_page import BasePage
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page


class LoginPage(BasePage):
    """Page Object for the application login screen."""

    _LOCATORS = {
        "login.email": (
            "#email",
            "id",
            {"id": "email", "tag": "input", "type": "email", "placeholder": "Email"},
            {"parent_selector": "form", "nth": 0},
        ),
        "login.password": (
            "#password",
            "id",
            {"id": "password", "tag": "input", "type": "password", "placeholder": "Password"},
            {"parent_selector": "form", "nth": 1},
        ),
        "login.submit": (
            "button[type='submit']",
            "css",
            {"tag": "button", "type": "submit", "text": "Login"},
            {"parent_selector": "form"},
        ),
        "login.error_message": (
            ".error-message",
            "css",
            {"tag": "div", "class": "error-message"},
        ),
        "login.remember_me": (
            "#remember",
            "id",
            {"id": "remember", "tag": "input", "type": "checkbox"},
        ),
    }

    def __init__(self, page: "Page") -> None:
        super().__init__(page)

    # ------------------------------------------------------------------
    # Page actions
    # ------------------------------------------------------------------

    def open(self, base_url: str) -> "LoginPage":
        self.navigate(f"{base_url.rstrip('/')}/login")
        logger.info("LoginPage opened at %s", self.url)
        return self

    def login(self, email: str, password: str) -> None:
        self.fill("login.email", email)
        self.fill("login.password", password)
        self.click("login.submit")
        logger.info("Submitted login for %s", email)

    def login_and_wait(self, email: str, password: str, success_url_fragment: str = "/dashboard") -> None:
        self.login(email, password)
        self.page.wait_for_url(f"**{success_url_fragment}**", timeout=15_000)

    def get_error(self) -> str:
        if self.is_visible("login.error_message"):
            return self.get_text("login.error_message")
        return ""

    def is_error_visible(self) -> bool:
        return self.is_visible("login.error_message")

    def check_remember_me(self) -> None:
        self.click("login.remember_me")
