"""
PRISM Popup / Modal component helper.

Wraps common modal/dialog patterns so page objects don't repeat the same
wait-confirm-dismiss logic. Works with both browser-native dialogs and
custom in-app modals.
"""
from __future__ import annotations

import contextlib
from typing import Callable, Optional, TYPE_CHECKING

from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page, Dialog, Locator


class PopupHandler:
    """Utility for handling both native browser dialogs and custom DOM modals."""

    # CSS selectors for common modal patterns (fallback list, tried in order)
    _MODAL_SELECTORS = [
        "[role='dialog']",
        ".modal",
        ".dialog",
        ".overlay",
        "#modal",
    ]

    def __init__(self, page: "Page") -> None:
        self.page = page
        self._last_dialog_message: Optional[str] = None
        self._dialog_handler_active = False

    # ------------------------------------------------------------------
    # Native browser dialog (alert / confirm / prompt)
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def expect_dialog(self, action: str = "accept", prompt_text: str = ""):
        """Context manager that auto-handles the next native dialog.

        Args:
            action: 'accept' or 'dismiss'.
            prompt_text: text to type into prompt dialogs (only used for 'accept').

        Example:
            with popup.expect_dialog("accept"):
                page.locator("#delete-btn").click()
        """
        def _handler(dialog: "Dialog") -> None:
            self._last_dialog_message = dialog.message
            logger.debug("Native dialog (%s): %r", dialog.type, dialog.message)
            if action == "accept":
                dialog.accept(prompt_text) if prompt_text else dialog.accept()
            else:
                dialog.dismiss()

        self.page.on("dialog", _handler)
        try:
            yield self
        finally:
            self.page.remove_listener("dialog", _handler)

    @property
    def last_dialog_message(self) -> Optional[str]:
        return self._last_dialog_message

    # ------------------------------------------------------------------
    # Custom DOM modals
    # ------------------------------------------------------------------

    def wait_for_modal(self, timeout: float = 10_000) -> "Locator":
        """Wait until a custom modal becomes visible; return its locator."""
        for sel in self._MODAL_SELECTORS:
            locator = self.page.locator(sel)
            try:
                locator.wait_for(state="visible", timeout=timeout)
                logger.debug("Modal detected via selector %r", sel)
                return locator
            except Exception:                                # noqa: BLE001
                continue
        raise TimeoutError(
            f"No modal became visible within {timeout}ms. "
            f"Tried: {self._MODAL_SELECTORS}"
        )

    def close_modal(self) -> None:
        """Dismiss the currently visible modal (ESC then button fallback)."""
        self.page.keyboard.press("Escape")
        # If ESC didn't close it, try common close buttons
        for sel in ("[aria-label='Close']", ".modal-close", ".close-btn", "button.close"):
            try:
                btn = self.page.locator(sel)
                if btn.is_visible():
                    btn.click()
                    return
            except Exception:                                # noqa: BLE001
                continue

    def get_modal_title(self) -> str:
        for sel in ("[role='dialog'] h1", "[role='dialog'] h2", ".modal-title", ".dialog-title"):
            try:
                el = self.page.locator(sel)
                if el.is_visible():
                    return el.inner_text()
            except Exception:                                # noqa: BLE001
                continue
        return ""

    def get_modal_body(self) -> str:
        for sel in ("[role='dialog'] .body", "[role='dialog'] p", ".modal-body"):
            try:
                el = self.page.locator(sel)
                if el.is_visible():
                    return el.inner_text()
            except Exception:                                # noqa: BLE001
                continue
        return ""

    def click_modal_button(self, label: str) -> None:
        """Click a button inside the modal by its visible text label."""
        for sel in self._MODAL_SELECTORS:
            try:
                modal = self.page.locator(sel)
                if modal.is_visible():
                    modal.get_by_role("button", name=label).click()
                    return
            except Exception:                                # noqa: BLE001
                continue
        raise RuntimeError(f"Modal button {label!r} not found in any open modal")

    def is_modal_visible(self) -> bool:
        for sel in self._MODAL_SELECTORS:
            try:
                if self.page.locator(sel).is_visible():
                    return True
            except Exception:                                # noqa: BLE001
                continue
        return False
