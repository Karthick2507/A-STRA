"""
ASTRA-v2 Allure Helper.

Thin wrappers around `allure-python-commons` so test and page code can
attach evidence (screenshots, API payloads, logs) without importing allure
directly — fails gracefully when allure is not installed.

Usage
─────
    from core.reporting.allure_helper import attach_screenshot, attach_json, allure_step

    with allure_step("Fill login form"):
        login_page.fill("login.email", "user@example.com")

    attach_screenshot(page, "after-login")
    attach_json(response.json(), "API response")
"""
from __future__ import annotations

import contextlib
import json
from typing import Any, Generator, Optional, TYPE_CHECKING

from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page

try:
    import allure                                             # type: ignore
    _ALLURE_OK = True
except ImportError:                                          # pragma: no cover
    _ALLURE_OK = False


# ──────────────────────────────────────────────────────────────────────────────
# Step context manager
# ──────────────────────────────────────────────────────────────────────────────

@contextlib.contextmanager
def allure_step(title: str) -> Generator[None, None, None]:
    """Context manager that wraps code in an Allure step (no-op if not installed)."""
    if _ALLURE_OK:
        with allure.step(title):
            yield
    else:
        yield


# ──────────────────────────────────────────────────────────────────────────────
# Attachments
# ──────────────────────────────────────────────────────────────────────────────

def attach_screenshot(page: "Page", name: str = "screenshot") -> None:
    """Capture a full-page screenshot and attach it to the Allure report."""
    try:
        screenshot_bytes = page.screenshot(full_page=True)
        if _ALLURE_OK:
            allure.attach(
                screenshot_bytes,
                name=name,
                attachment_type=allure.attachment_type.PNG,
            )
    except Exception as exc:                                 # noqa: BLE001
        logger.debug("allure_helper.attach_screenshot failed: %s", exc)


def attach_json(data: Any, name: str = "json") -> None:
    """Attach a JSON-serialisable object to the Allure report."""
    try:
        body = json.dumps(data, indent=2, default=str)
        if _ALLURE_OK:
            allure.attach(
                body,
                name=name,
                attachment_type=allure.attachment_type.JSON,
            )
    except Exception as exc:                                 # noqa: BLE001
        logger.debug("allure_helper.attach_json failed: %s", exc)


def attach_text(text: str, name: str = "text") -> None:
    """Attach plain text to the Allure report."""
    try:
        if _ALLURE_OK:
            allure.attach(
                text,
                name=name,
                attachment_type=allure.attachment_type.TEXT,
            )
    except Exception as exc:                                 # noqa: BLE001
        logger.debug("allure_helper.attach_text failed: %s", exc)


def attach_html(html: str, name: str = "html") -> None:
    try:
        if _ALLURE_OK:
            allure.attach(
                html,
                name=name,
                attachment_type=allure.attachment_type.HTML,
            )
    except Exception as exc:                                 # noqa: BLE001
        logger.debug("allure_helper.attach_html failed: %s", exc)


def attach_trace(trace_path: str, name: str = "playwright-trace") -> None:
    """Attach a Playwright trace .zip to the Allure report."""
    try:
        import pathlib
        data = pathlib.Path(trace_path).read_bytes()
        if _ALLURE_OK:
            allure.attach(
                data,
                name=name,
                attachment_type=allure.attachment_type.ZIP,
            )
    except Exception as exc:                                 # noqa: BLE001
        logger.debug("allure_helper.attach_trace failed: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Decorators
# ──────────────────────────────────────────────────────────────────────────────

def allure_title(title: str):
    """Decorator: set Allure test title."""
    if _ALLURE_OK:
        return allure.title(title)
    def _noop(fn):
        return fn
    return _noop


def allure_description(desc: str):
    """Decorator: set Allure test description."""
    if _ALLURE_OK:
        return allure.description(desc)
    def _noop(fn):
        return fn
    return _noop


def allure_severity(severity: str):
    """Decorator: set Allure severity (blocker, critical, normal, minor, trivial)."""
    if _ALLURE_OK:
        severity_map = {
            "blocker":  allure.severity_level.BLOCKER,
            "critical": allure.severity_level.CRITICAL,
            "normal":   allure.severity_level.NORMAL,
            "minor":    allure.severity_level.MINOR,
            "trivial":  allure.severity_level.TRIVIAL,
        }
        level = severity_map.get(severity.lower(), allure.severity_level.NORMAL)
        return allure.severity(level)
    def _noop(fn):
        return fn
    return _noop
