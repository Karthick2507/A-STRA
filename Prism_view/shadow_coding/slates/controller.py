"""
controller slate — corporate template for test controller / orchestrator style.

Drop your real corporate controller/fixture file here.
PRISM will parse the style and apply it when generating {entity}_Controller.py output files.

Role: controller → drives {entity}_Controller.py generation
"""
from __future__ import annotations

import logging

from typing import Generator

import pytest
from playwright.sync_api import Page, Browser, BrowserContext

logger = logging.getLogger(__name__)


class ExampleController:
    """Corporate test controller that wires together page objects."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def setup(self) -> None:
        logger.info("Controller setup")

    def teardown(self) -> None:
        logger.info("Controller teardown")


@pytest.fixture
def controller(page: Page) -> Generator[ExampleController, None, None]:
    ctrl = ExampleController(page)
    ctrl.setup()
    yield ctrl
    ctrl.teardown()
