"""
ASTRA-v2 Shadow Coding — Code Enhancer.

Post-processes the raw `playwright codegen --target python-pytest` output
into ASTRA-v2 POM style:

  1. Replace bare `page.locator(...)` calls with `pom.find(...)` calls
  2. Detect fill + click patterns and replace with `pom.fill()` / `pom.click()`
  3. Auto-insert assertions at:
       - URL change points (`page.goto(...)` lines)
       - After the final action in the script
  4. Extract unique selectors and register them as _LOCATORS entries
  5. Wrap everything in a proper pytest test function

Raw codegen output example
──────────────────────────
    def test_example(page: Page) -> None:
        page.goto("https://app.example.com/login")
        page.locator("#email").fill("user@example.com")
        page.locator("#password").fill("secret")
        page.locator("button[type='submit']").click()

Enhanced output
───────────────
    from UI.pages.base_page import BasePage

    def test_shadow_<session_id>(page):
        pom = BasePage(page)
        pom.navigate("https://app.example.com/login")
        pom.fill("login_email", "user@example.com")
        pom.fill("login_password", "secret")
        pom.click("login_submit")
        assert page.locator("text=Dashboard").is_visible()
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CodeEnhancer:
    """Transform raw playwright codegen output into ASTRA POM test code."""

    _FILL_RE   = re.compile(r'page\.locator\((["\'])(.+?)\1\)\.fill\((["\'])(.+?)\3\)')
    _CLICK_RE  = re.compile(r'page\.locator\((["\'])(.+?)\1\)\.click\(\)')
    _GOTO_RE   = re.compile(r'page\.goto\((["\'])(.+?)\1\)')
    _SELECT_RE = re.compile(r'page\.locator\((["\'])(.+?)\1\)\.select_option\((["\'])(.+?)\3\)')
    _ASSERT_RE = re.compile(r'expect\(page\)\.to_have_url\((["\'])(.+?)\1\)')

    def __init__(
        self,
        session_id:    str = "shadow",
        page_class:    str = "BasePage",
        page_import:   str = "from UI.pages.base_page import BasePage",
        goal_text:     Optional[str] = None,
        goal_selector: Optional[str] = None,
    ) -> None:
        self.session_id    = session_id
        self.page_class    = page_class
        self.page_import   = page_import
        self.goal_text     = goal_text
        self.goal_selector = goal_selector
        self._name_counter: Dict[str, int] = {}

    def enhance(self, raw_code: str) -> str:
        """Return the enhanced POM-style test code as a string."""
        lines  = raw_code.splitlines()
        output: List[str] = []

        output.append(self.page_import)
        output.append("import pytest")
        output.append("")
        output.append("")
        output.append(f"def test_shadow_{self.session_id}(page):")
        output.append(f"    pom = {self.page_class}(page)")
        output.append("")

        prev_url = ""
        for line in lines:
            stripped = line.strip()

            # Skip function def, type hints, imports, blank setup lines
            if (
                stripped.startswith("def test_")
                or stripped.startswith("from playwright")
                or stripped.startswith("import ")
                or stripped == ""
                or stripped.startswith("page: Page")
            ):
                continue

            # navigate / goto
            m = self._GOTO_RE.search(stripped)
            if m:
                url = m.group(2)
                output.append(f'    pom.navigate("{url}")')
                if prev_url and prev_url != url:
                    fragment = _url_fragment(url)
                    if fragment:
                        output.append(f'    assert "{fragment}" in page.url')
                prev_url = url
                continue

            # fill
            m = self._FILL_RE.search(stripped)
            if m:
                sel, val = m.group(2), m.group(4)
                name = self._logical_name(sel)
                output.append(f'    pom.fill("{name}", {val!r})')
                continue

            # click
            m = self._CLICK_RE.search(stripped)
            if m:
                sel = m.group(2)
                name = self._logical_name(sel)
                output.append(f'    pom.click("{name}")')
                continue

            # select_option
            m = self._SELECT_RE.search(stripped)
            if m:
                sel, val = m.group(2), m.group(4)
                name = self._logical_name(sel)
                output.append(f'    pom.select("{name}", {val!r})')
                continue

            # expect URL assertion — convert to plain assert
            m = self._ASSERT_RE.search(stripped)
            if m:
                url_pattern = m.group(2)
                output.append(f'    assert "{_url_fragment(url_pattern)}" in page.url')
                continue

            # Pass through any other lines with proper indentation
            if stripped and not stripped.startswith("#"):
                output.append(f"    # {stripped}")   # comment out unknowns

        # Final goal assertions
        output.append("")
        if self.goal_text:
            output.append(f'    assert page.locator("text={self.goal_text}").is_visible()')
        if self.goal_selector:
            output.append(f'    assert page.locator("{self.goal_selector}").is_visible()')

        return "\n".join(output) + "\n"

    def enhance_file(self, raw_path: str | Path, output_path: Optional[str | Path] = None) -> Path:
        """Read raw codegen file, enhance, write to output_path (or same dir)."""
        raw = Path(raw_path).read_text(encoding="utf-8")
        enhanced = self.enhance(raw)

        if output_path is None:
            output_path = Path(raw_path).with_name(
                Path(raw_path).stem.replace("_raw", "") + "_enhanced.py"
            )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(enhanced, encoding="utf-8")
        return out

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _logical_name(self, selector: str) -> str:
        """Convert a raw CSS/ID selector into a stable logical name."""
        # #email → "email", [name='q'] → "q", button[type='submit'] → "submit_btn"
        m = re.match(r"#([\w-]+)", selector)
        if m:
            return m.group(1).replace("-", "_")

        m = re.match(r"\[name=['\"](.+?)['\"]\]", selector)
        if m:
            return m.group(1).replace("-", "_")

        m = re.search(r"\[type=['\"](.+?)['\"]\]", selector)
        if m and m.group(1) not in ("text", "password", "email"):
            return f"{m.group(1)}_btn"

        # fallback: sanitise selector to identifier
        name = re.sub(r"[^a-z0-9]", "_", selector.lower()).strip("_")
        name = re.sub(r"_+", "_", name)[:40]
        count = self._name_counter.get(name, 0)
        self._name_counter[name] = count + 1
        return name if count == 0 else f"{name}_{count}"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _url_fragment(url: str) -> str:
    path = url.split("?")[0].split("#")[0]
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else ""
