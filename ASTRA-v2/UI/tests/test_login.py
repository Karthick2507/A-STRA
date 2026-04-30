"""
ASTRA-v2 example UI test — Login flow.

Demonstrates:
  - BasePage / LoginPage POM pattern
  - Self-healing locators (transparent — no test code changes if selector breaks)
  - PopupHandler for error dialogs
  - Data-driven test with pytest parametrize
"""
import json
from pathlib import Path

import pytest

from UI.pages.login_page import LoginPage
from UI.components.popup import PopupHandler
from core.config import CONFIG


# Load test data from Data/UI/login_data.json
_DATA_FILE = Path("Data/UI/login_data.json")
_DATA: dict = json.loads(_DATA_FILE.read_text()) if _DATA_FILE.exists() else {}


@pytest.fixture
def login_page(page):
    return LoginPage(page)


@pytest.fixture
def base_url() -> str:
    return CONFIG.environments[CONFIG.default_env]["base_url"]


class TestLogin:
    """Happy-path and error-path login scenarios."""

    def test_successful_login(self, login_page: LoginPage, base_url: str) -> None:
        login_page.open(base_url)
        login_page.login(
            email=_DATA.get("email", "testuser@example.com"),
            password=_DATA.get("password", "Test@1234"),
        )
        assert "dashboard" in login_page.page.url.lower() or \
               login_page.page.locator("text=Welcome").is_visible()

    def test_invalid_credentials_shows_error(
        self, login_page: LoginPage, base_url: str
    ) -> None:
        login_page.open(base_url)
        login_page.login(
            email=_DATA.get("invalid_email", "wrong@example.com"),
            password=_DATA.get("invalid_password", "wrongpassword"),
        )
        assert login_page.is_error_visible(), "Expected error message after invalid login"
        error_text = login_page.get_error()
        assert error_text, "Error message should not be empty"

    def test_empty_email_blocked(self, login_page: LoginPage, base_url: str) -> None:
        login_page.open(base_url)
        login_page.fill("login.password", "anypassword")
        login_page.click("login.submit")
        # Browser validation should prevent submission — URL should stay on login
        assert "login" in login_page.page.url.lower() or login_page.is_error_visible()

    @pytest.mark.parametrize("email,password", [
        ("", "Test@1234"),
        ("testuser@example.com", ""),
        ("not-an-email", "Test@1234"),
    ])
    def test_invalid_inputs_rejected(
        self,
        login_page: LoginPage,
        base_url: str,
        email: str,
        password: str,
    ) -> None:
        login_page.open(base_url)
        if email:
            login_page.fill("login.email", email)
        if password:
            login_page.fill("login.password", password)
        login_page.click("login.submit")
        assert "login" in login_page.page.url.lower() or login_page.is_error_visible()

    def test_remember_me_checkbox(self, login_page: LoginPage, base_url: str) -> None:
        login_page.open(base_url)
        login_page.check_remember_me()
        assert login_page.find("login.remember_me").is_checked()
