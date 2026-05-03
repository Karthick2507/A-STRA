"""
PRISM TabPanel component helper.

Abstracts tabbed-interface interactions for both ARIA-role tabs and common
CSS tab patterns.
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator


class TabPanel:
    """Utility for interacting with tabbed UI sections."""

    _TAB_LIST_SELECTORS = [
        "[role='tablist']",
        ".tab-list",
        ".tabs",
        ".nav-tabs",
    ]

    def __init__(self, page: "Page", container_selector: Optional[str] = None) -> None:
        self.page = page
        self._container = container_selector

    def _tablist(self) -> "Locator":
        scope = self.page.locator(self._container) if self._container else self.page
        for sel in self._TAB_LIST_SELECTORS:
            try:
                tl = scope.locator(sel)
                if tl.is_visible():
                    return tl
            except Exception:                                # noqa: BLE001
                continue
        raise RuntimeError("No tab list found on the page")

    def get_tab_names(self) -> List[str]:
        """Return visible text of all tabs."""
        try:
            tabs = self._tablist().locator("[role='tab'], .tab, li")
            count = tabs.count()
            return [tabs.nth(i).inner_text().strip() for i in range(count)]
        except Exception as exc:                             # noqa: BLE001
            logger.debug("TabPanel.get_tab_names failed: %s", exc)
            return []

    def click_tab(self, name: str) -> None:
        """Activate the tab whose visible text matches `name` (case-insensitive)."""
        tabs = self._tablist().locator("[role='tab'], .tab, li")
        count = tabs.count()
        for i in range(count):
            tab = tabs.nth(i)
            if tab.inner_text().strip().lower() == name.lower():
                tab.click()
                logger.debug("Clicked tab %r", name)
                return
        raise ValueError(f"Tab {name!r} not found. Available: {self.get_tab_names()}")

    def get_active_tab(self) -> Optional[str]:
        """Return the name of the currently active tab."""
        for sel in (
            "[role='tab'][aria-selected='true']",
            ".tab.active",
            ".nav-link.active",
        ):
            try:
                el = self.page.locator(sel)
                if el.is_visible():
                    return el.inner_text().strip()
            except Exception:                                # noqa: BLE001
                continue
        return None

    def get_active_panel_content(self) -> str:
        """Return the inner text of the currently visible tab panel."""
        for sel in (
            "[role='tabpanel']:not([hidden])",
            ".tab-pane.active",
            ".tab-content .active",
        ):
            try:
                el = self.page.locator(sel)
                if el.is_visible():
                    return el.inner_text()
            except Exception:                                # noqa: BLE001
                continue
        return ""

    def wait_for_tab_content(self, tab_name: str, timeout: float = 10_000) -> str:
        """Click `tab_name`, wait for its panel to load, return panel text."""
        self.click_tab(tab_name)
        self.page.wait_for_timeout(300)                      # brief settle
        content = self.get_active_panel_content()
        if not content:
            self.page.wait_for_function(
                "() => document.querySelector('[role=\"tabpanel\"]:not([hidden]),"
                " .tab-pane.active')?.innerText?.trim().length > 0",
                timeout=timeout,
            )
            content = self.get_active_panel_content()
        return content
