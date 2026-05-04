"""
ui_locator slate — corporate template for locator definitions.

Drop your real corporate locator file here.
PRISM will parse the style and apply it when generating {entity}_Locators.py output files.

Role: ui_locator → drives {entity}_Locators.py generation
"""
from __future__ import annotations

import logging

from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class ExampleLocators:
    """Centralised locator definitions in corporate style."""

    SUBMIT_BUTTON = "button[type='submit']"
    SEARCH_INPUT  = "input[name='search']"
    NAV_MENU      = "nav[role='navigation']"

    def __init__(self, page: Page) -> None:
        self.page = page

    def submit_btn(self):
        return self.page.locator(self.SUBMIT_BUTTON)

    def search_input(self):
        return self.page.get_by_role("textbox", name="Search")
