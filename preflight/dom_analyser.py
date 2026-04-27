"""ASTRA DOM analyser - scans browser DOM to extract form fields and structure."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from playwright.sync_api import Page
from utils.env_loader import ENV
from utils.logger import logger


class DomAnalyser:
    def __init__(self, page: Page) -> None:
        self.page = page

    def analyse(self) -> Dict[str, Any]:
        logger.preflight("DomAnalyser: scanning DOM for form fields...")
        fields = self._extract_form_fields()
        logger.preflight(f"  Found {len(fields)} form fields")
        return {"fields": fields, "status": "PASS"}

    def _extract_form_fields(self) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []

        # Find all form inputs
        selectors = [
            "input:not([type=hidden]):not([type=submit]):not([type=button])",
            "select",
            "textarea",
        ]

        for selector in selectors:
            elements = self.page.query_selector_all(selector)
            for el in elements:
                try:
                    name = (
                        el.get_attribute("name")
                        or el.get_attribute("id")
                        or el.get_attribute("data-testid")
                    )
                    if not name:
                        continue

                    field_type = el.get_attribute("type") or "text"
                    if field_type == "hidden":
                        continue

                    label = ""
                    label_el = self.page.query_selector(f"label[for='{el.get_attribute('id')}']") if el.get_attribute(
                        "id"
                    ) else None
                    if label_el:
                        label = label_el.text_content() or ""

                    required = el.get_attribute("required") is not None
                    placeholder = el.get_attribute("placeholder") or ""

                    field = {
                        "name": name,
                        "id": el.get_attribute("id") or "",
                        "type": field_type,
                        "label": label or placeholder,
                        "placeholder": placeholder,
                        "required": required,
                        "selector": f"[name='{name}']",
                    }

                    if field_type == "select":
                        options = el.query_selector_all("option")
                        field["options"] = [opt.text_content() or "" for opt in options]

                    fields.append(field)
                except Exception as exc:
                    logger.warning(f"Error extracting field: {exc}")
                    continue

        return fields


async def run_dom_analyser(
    page: Page,
    target_url: str,
    username: str,
    password: str,
) -> Dict[str, Any]:
    """9-step DOM analysis process."""
    logger.preflight("\n" + "=" * 60)
    logger.preflight("Step 1/9: Launching browser...")

    logger.preflight("Step 2/9: Logging in...")
    page.goto(ENV.LOGIN_URL)
    page.fill("[name=username], [name=email]", username)
    page.fill("[name=password]", password)
    page.click("[type=submit]")
    page.wait_for_load_state("networkidle")

    logger.preflight("Step 3/9: Navigating to target page...")
    page.goto(target_url)
    page.wait_for_load_state("networkidle")

    logger.preflight("Step 4/9: Waiting for page stability...")
    page.wait_for_timeout(1000)

    logger.preflight("Step 5/9: Interacting with page...")
    # Try to trigger any dynamic form reveals
    selectors_to_click = ["button", "[type=button]", "[role=button]"]
    for sel in selectors_to_click:
        buttons = page.query_selector_all(sel)
        if buttons:
            try:
                buttons[0].click()
                page.wait_for_timeout(500)
            except Exception:
                pass

    logger.preflight("Step 6/9: Taking screenshot...")
    page.screenshot(path="reports/dom_scan.png")

    logger.preflight("Step 7/9: Scrolling page...")
    page.evaluate("() => window.scrollBy(0, window.innerHeight)")
    page.wait_for_timeout(500)

    logger.preflight("Step 8/9: Waiting for inputs...")
    page.wait_for_selector("input, select, textarea", timeout=5000)

    logger.preflight("Step 9/9: Scanning DOM...")
    analyser = DomAnalyser(page)
    return analyser.analyse()
