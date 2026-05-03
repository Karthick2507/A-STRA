"""
PRISM Tooltip component helper.

Handles both CSS :hover-triggered tooltips and ARIA-described tooltips.
Hover-reveal is done via JS mouse-over because Playwright's hover() can be
unreliable for CSS-transition tooltips on headless browsers.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator


class TooltipHelper:
    """Utility for triggering and reading tooltip text."""

    _TOOLTIP_SELECTORS = [
        "[role='tooltip']",
        ".tooltip",
        ".tippy-box",
        "[data-tooltip]",
        "[title]",
    ]

    def __init__(self, page: "Page") -> None:
        self.page = page

    def hover_and_get_text(
        self,
        trigger_selector: str,
        timeout: float = 3_000,
    ) -> Optional[str]:
        """Hover over `trigger_selector` and return the tooltip text.

        Returns None if no tooltip appears within `timeout` ms.
        """
        try:
            trigger = self.page.locator(trigger_selector)
            trigger.hover()
        except Exception as exc:                             # noqa: BLE001
            logger.debug("TooltipHelper hover failed: %s", exc)
            return None

        for sel in self._TOOLTIP_SELECTORS:
            try:
                tip = self.page.locator(sel)
                tip.wait_for(state="visible", timeout=timeout)
                return tip.inner_text()
            except Exception:                                # noqa: BLE001
                continue

        # Fallback: try aria-describedby
        try:
            trigger_el = self.page.locator(trigger_selector)
            described_by = trigger_el.get_attribute("aria-describedby")
            if described_by:
                return self.page.locator(f"#{described_by}").inner_text()
        except Exception:                                    # noqa: BLE001
            pass

        # Fallback: title attribute
        try:
            return self.page.locator(trigger_selector).get_attribute("title")
        except Exception:                                    # noqa: BLE001
            return None

    def get_tooltip_for_locator(self, locator: "Locator") -> Optional[str]:
        """Convenience wrapper accepting a Locator instead of a selector string."""
        try:
            locator.hover()
            for sel in self._TOOLTIP_SELECTORS:
                try:
                    tip = self.page.locator(sel)
                    tip.wait_for(state="visible", timeout=2_000)
                    return tip.inner_text()
                except Exception:                            # noqa: BLE001
                    continue
        except Exception:                                    # noqa: BLE001
            pass
        return None

    def is_tooltip_visible(self) -> bool:
        for sel in self._TOOLTIP_SELECTORS:
            try:
                if self.page.locator(sel).is_visible():
                    return True
            except Exception:                                # noqa: BLE001
                continue
        return False
