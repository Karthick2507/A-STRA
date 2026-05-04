"""
ui_page slate — corporate template for base page / page object structure.

Drop your real corporate BasePage here.
PRISM will parse the style and apply it when generating Base_page.py output files.

Role: ui_page → drives Base_page.py generation
"""
from __future__ import annotations

import logging

from playwright.sync_api import Page, expect

logger = logging.getLogger(__name__)


class BasePage:
    """Corporate base page object."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def navigate(self, url: str) -> None:
        logger.info(f"Navigating to {url}")
        self.page.goto(url)

    def wait_for_load(self) -> None:
        self.page.wait_for_load_state("networkidle")
