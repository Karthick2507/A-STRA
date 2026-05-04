"""
ui_action slate — corporate template for UI action methods.

Drop your real corporate UI action file here.
PRISM will parse the style (imports, base class, logging, naming) and
apply it when generating {entity}_UI.py output files.

Role: ui_action → drives {entity}_UI.py generation
"""
from __future__ import annotations

import logging

from typing import Optional

from Base_page import BasePage

logger = logging.getLogger(__name__)


class ExampleActionPage(BasePage):
    """Example UI action page object in corporate style."""

    def click_submit(self) -> None:
        logger.info(f"Clicking submit button")
        self.page.get_by_role("button", name="Submit").click()

    def fill_search(self, query: str) -> None:
        logger.info(f"Filling search field with: {query}")
        self.page.get_by_role("textbox", name="Search").fill(query)
