"""PRISM Page Object Model pages."""
from UI.pages.base_page import BasePage, LocatorHealingError, LocatorNotRegisteredError
from UI.pages.login_page import LoginPage
from UI.pages.menu_page import MenuPage

__all__ = [
    "BasePage", "LocatorHealingError", "LocatorNotRegisteredError",
    "LoginPage", "MenuPage",
]
