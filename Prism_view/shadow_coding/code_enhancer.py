"""
PRISM Shadow Coding — Corporate Code Enhancer.

Transforms raw ``playwright codegen --target python-pytest`` output into
corporate pytest-style files driven by the active slate roles in style_profile.json.

Core output (always):
    {name}_UI.py      — UI page-object + action orchestration class  (ui_action)
    {name}_Data.json  — Extracted test data                          (data_verify)
    Base_page.py      — Reusable base methods                        (ui_page)

Extended output (emitted when by_role profile is present for the role):
    {name}_Locators.py    — Centralised locator definitions          (ui_locator)
    {name}_Controller.py  — Controller wiring page objects together  (controller)
    {name}_test.py        — API / integration test scaffold          (api_test)

Raw input example (playwright codegen output)
─────────────────────────────────────────────
    def test_example(page: Page) -> None:
        page.goto("https://mrm.stg.example.tv/login")
        page.get_by_role("textbox", name="Login Name").fill("user@email.com")
        page.get_by_role("textbox", name="Password").fill("Fwadmin@999")
        page.get_by_role("button", name="Log in").click()
        page.get_by_role("link", name="Network Items").click()
        page.get_by_role("link", name="Videos").click()
        page.get_by_role("button", name="add_circle_outline Create").click()
        page.get_by_role("textbox", name="Video Title").fill("TestRUN")
        page.get_by_role("textbox", name="Description").fill("Test Run")
        page.get_by_role("textbox", name="Please select a date").first.click()
        page.get_by_text("30", exact=True).click()
        page.get_by_role("button", name="Apply").click()
        page.get_by_role("button", name="Create Video").click()
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Style profile loader ───────────────────────────────────────────────────────

_PROFILE_PATH = Path("Prism_view/shadow_coding/style_profile.json")


def _load_profile() -> Dict:
    """Load style_profile.json if present; return empty dict for full fallback."""
    if _PROFILE_PATH.exists():
        try:
            with open(_PROFILE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


_PROFILE: Dict = _load_profile()


def _active_roles() -> set:
    """Return the set of roles that have a non-null by_role profile entry."""
    by_role = _PROFILE.get("by_role", {})
    return {role for role, prof in by_role.items() if prof is not None and not role.startswith("_")}


def _role_profile(role: str) -> Dict:
    """Return the style sub-profile for a role, falling back to top-level profile."""
    return _PROFILE.get("by_role", {}).get(role) or _PROFILE


# ── Regex patterns ─────────────────────────────────────────────────────────────

_GOTO    = re.compile(r'page\.goto\(["\'](.+?)["\']\)')
_ROLE    = re.compile(r'page\.get_by_role\(["\'](\w+)["\'],\s*name=["\'](.+?)["\']\)')
_TESTID  = re.compile(r'page\.get_by_test_id\(["\'](.+?)["\']\)')
_LABEL   = re.compile(r'page\.get_by_label\(["\'](.+?)["\']\)')
_PHOLDER = re.compile(r'page\.get_by_placeholder\(["\'](.+?)["\']\)')
_TEXT    = re.compile(r'page\.get_by_text\(["\'](.+?)["\']')
_FILL    = re.compile(r'\.fill\(["\'](.+?)["\']\)')
_CLICK   = re.compile(r'\.click\(\)')
_CHECK   = re.compile(r'\.check\(\)')
_SELECT  = re.compile(r'\.select_option\(["\'](.+?)["\']\)')

_LOGIN_NAME = re.compile(r'login\s*name', re.IGNORECASE)
_PASSWORD   = re.compile(r'^password$', re.IGNORECASE)
_LOG_IN     = re.compile(r'^log\s*in$', re.IGNORECASE)
_CREATE_BTN = re.compile(r'create|add_circle', re.IGNORECASE)
_DATE_FIELD = re.compile(r'date|calendar', re.IGNORECASE)
_APPLY_BTN  = re.compile(r'^apply$', re.IGNORECASE)
_NAV_SKIP   = re.compile(r'network\s*items|home|back|menu', re.IGNORECASE)

# Common field-label → PascalCase dict-key mapping
_FIELD_MAP: Dict[str, str] = {
    "video title":           "Title1",
    "title":                 "Title1",
    "title 1":               "Title1",
    "title1":                "Title1",
    "audience name":         "Name",
    "name":                  "Name",
    "description":           "Description",
    "external asset id":     "ExternalAssetID",
    "external id":           "ExternalAssetID",
    "start date":            "StartDate",
    "end date":              "EndDate",
    "please select a date":  "StartDate",
    "content owner":         "ContentOwner",
    "parent series":         "ParentSeries",
    "parent groups":         "ParentGroups",
    "label":                 "Label",
    "type":                  "Type",
    "status":                "Status",
}


def _to_field_key(label: str, testid: str = "") -> str:
    """Map a locator label/testid → corporate PascalCase dict key."""
    low = label.lower().strip()
    if low in _FIELD_MAP:
        return _FIELD_MAP[low]
    if testid:
        return "".join(w.capitalize() for w in re.split(r"[\s_\-]+", testid))
    return "".join(w.capitalize() for w in re.split(r"[\s_\-]+", label))


def _entity_nav_key(plural: str) -> str:
    return plural.lower().replace(" ", "_")


def _singular(plural: str) -> str:
    """Crude singularisation: strip trailing 's' if present."""
    if plural.lower().endswith("ies"):
        return plural[:-3] + "y"
    if plural.lower().endswith("ses"):
        return plural[:-2]
    if plural.lower().endswith("s") and len(plural) > 2:
        return plural[:-1]
    return plural


# ── Internal parse model ───────────────────────────────────────────────────────

@dataclass
class _ParsedLine:
    raw:          str
    locator:      str = ""      # role | testid | label | placeholder | text | goto
    role:         str = ""
    name_attr:    str = ""
    testid:       str = ""
    fill_value:   Optional[str] = None
    select_value: Optional[str] = None
    is_click:     bool = False
    is_check:     bool = False


@dataclass
class _FormField:
    key:          str
    value:        str
    locator_code: str           # e.g. self.page.get_by_role("textbox", name="Video Title")


@dataclass
class _Script:
    start_url:     str = ""
    username:      str = ""
    password:      str = ""
    entity_plural: str = "Items"    # e.g. "Videos"
    entity_name:   str = "Item"     # e.g. "Video"
    nav_key:       str = "items"    # e.g. "videos"
    network_name:  str = "YourNetwork"
    form_fields:   List[_FormField] = field(default_factory=list)
    has_date:      bool = False
    extra_sections: List[str] = field(default_factory=list)  # post-create optional sections


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_raw(raw_code: str) -> List[_ParsedLine]:
    result: List[_ParsedLine] = []
    for raw_line in raw_code.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^(def test_|from playwright|^import )", stripped):
            continue
        if stripped in (")", ""):
            continue

        pl = _ParsedLine(raw=stripped)

        m = _GOTO.search(stripped)
        if m:
            pl.locator = "goto"
            pl.fill_value = m.group(1)
            result.append(pl)
            continue

        m = _ROLE.search(stripped)
        if m:
            pl.role = m.group(1)
            pl.name_attr = m.group(2)
            pl.locator = "role"

        m = _TESTID.search(stripped)
        if m:
            pl.testid = m.group(1)
            if not pl.locator:
                pl.locator = "testid"

        m = _LABEL.search(stripped)
        if m and not pl.locator:
            pl.name_attr = m.group(1)
            pl.locator = "label"

        m = _PHOLDER.search(stripped)
        if m and not pl.locator:
            pl.name_attr = m.group(1)
            pl.locator = "placeholder"

        m = _TEXT.search(stripped)
        if m and not pl.locator:
            pl.name_attr = m.group(1)
            pl.locator = "text"

        m = _FILL.search(stripped)
        if m:
            pl.fill_value = m.group(1)

        m = _SELECT.search(stripped)
        if m:
            pl.select_value = m.group(1)

        if _CLICK.search(stripped):
            pl.is_click = True
        if _CHECK.search(stripped):
            pl.is_check = True

        if pl.locator:
            result.append(pl)

    return result


def _build_locator_code(pl: _ParsedLine) -> str:
    """Return the self.page.get_by_*(...) expression for a parsed line."""
    if pl.locator == "role":
        return f'self.page.get_by_role("{pl.role}", name="{pl.name_attr}")'
    if pl.locator == "testid":
        return f'self.page.get_by_test_id("{pl.testid}")'
    if pl.locator == "label":
        return f'self.page.get_by_label("{pl.name_attr}")'
    if pl.locator == "placeholder":
        return f'self.page.get_by_placeholder("{pl.name_attr}")'
    if pl.locator == "text":
        return f'self.page.get_by_text("{pl.name_attr}", exact=True)'
    return f'self.page.locator("{pl.name_attr}")'


def _classify(lines: List[_ParsedLine]) -> _Script:
    s = _Script()
    create_seen = False
    in_form = False
    submit_done = False

    for pl in lines:
        name = pl.name_attr or ""
        val  = pl.fill_value

        # ── URL ──────────────────────────────────────────────────────────
        if pl.locator == "goto":
            if not s.start_url:
                s.start_url = val or ""
            continue

        # ── Login block ───────────────────────────────────────────────────
        if _LOGIN_NAME.search(name) and val:
            s.username = val
            continue
        if _PASSWORD.search(name) and val:
            s.password = val
            continue
        if _LOG_IN.search(name) and pl.is_click:
            continue

        # ── Navigation links → detect entity ─────────────────────────────
        if pl.role == "link" and pl.is_click:
            if not _NAV_SKIP.search(name):
                s.entity_plural = name
                s.entity_name   = _singular(name)
                s.nav_key       = _entity_nav_key(name)
            continue

        # ── Create button (opens form) ────────────────────────────────────
        if (
            pl.role == "button"
            and pl.is_click
            and _CREATE_BTN.search(name)
            and not create_seen
            and not submit_done
        ):
            create_seen = True
            in_form = True
            continue

        # ── Date picker interactions ──────────────────────────────────────
        if in_form and not submit_done:
            if _DATE_FIELD.search(name) or (pl.locator == "text" and re.match(r"^\d+$", name)):
                s.has_date = True
                continue
            if _APPLY_BTN.search(name) and pl.is_click:
                continue

        # ── Form fill actions ─────────────────────────────────────────────
        if in_form and not submit_done and val:
            label = name if name else (pl.testid or "")
            key = _to_field_key(label, pl.testid)
            loc = _build_locator_code(pl)
            s.form_fields.append(_FormField(key=key, value=val, locator_code=loc))
            continue

        # ── Submit button (final Create X / Save) ─────────────────────────
        if (
            in_form
            and pl.role == "button"
            and pl.is_click
            and re.search(r'\b(create|save|submit|add)\b', name, re.IGNORECASE)
        ):
            submit_done = True
            in_form = False
            continue

    return s


# ── Code generation ────────────────────────────────────────────────────────────

def _gen_ui_py(s: _Script) -> str:
    """Generate {entity_plural}_UI.py content."""

    # Build example data for docstring (indent=4, then re-indent to fit in docstring)
    example_data = {s.entity_plural: [{f.key: f.value for f in s.form_fields}]}
    _raw_json = json.dumps(example_data, indent=4)
    example_json = "\n            ".join(_raw_json.splitlines())

    # Build form-fill lines
    fill_lines: List[str] = []
    for f in s.form_fields:
        fill_lines.append(
            f'                {f.locator_code}.clear()\n'
            f'                {f.locator_code}.fill(item["{f.key}"])'
        )
    fill_block = "\n".join(fill_lines) if fill_lines else "                pass  # TODO: add field fills"

    # Optional date block
    if s.has_date:
        date_block = (
            '                year = str(datetime.now().year - 1)\n'
            '                date_input = self.page.get_by_role("textbox", name="Please select a date").first\n'
            '                date_input.click()\n'
            '                self.page.get_by_role("button", name=year).click()\n'
            '                self.page.get_by_text("1", exact=True).click()\n'
            '                self.page.get_by_role("button", name="Apply").click()'
        )
        date_import = "from datetime import datetime\n"
    else:
        date_block = ""
        date_import = ""

    # Combine fill + date
    body_parts: List[str] = []
    if fill_block:
        body_parts.append(fill_block)
    if date_block:
        body_parts.append(date_block)
    full_body = "\n".join(body_parts) if body_parts else "                pass  # TODO: add actions"

    # Optional field checks (any field beyond the first two gets an if-guard scaffold)
    optional_checks: List[str] = []
    for f in s.form_fields[2:]:
        optional_checks.append(
            f'            if "{f.key}" in item:\n'
            f'                {f.locator_code}.fill(item["{f.key}"])'
        )
    optional_block = ("\n" + "\n".join(optional_checks)) if optional_checks else ""

    cls = s.entity_plural
    nav = s.nav_key
    entity = s.entity_name

    # Pull profile values (fall back to defaults if profile absent)
    _st  = _PROFILE.get("structure", {})
    _imp = _PROFILE.get("imports", {})
    _base_class        = _st.get("base_class",        "BasePage")
    _base_import       = _st.get("base_class_import", "from Base_page import BasePage")
    _logging_init      = _st.get("logging_init",      "logger = logging.getLogger(__name__)")
    _logging_call      = _st.get("logging_call",      "logger.info")
    _header_imports    = "\n".join(_imp.get("header",  ["from __future__ import annotations"]))
    _stdlib_imports    = "\n".join(_imp.get("stdlib",  ["import logging"]))
    _typing_imports    = "\n".join(_imp.get("typing",  ["from typing import Dict, List, Optional"]))

    return f'''"""
{cls} page object and action orchestration.

Generated by PRISM Shadow Coding enhancer.
"""
{_header_imports}

{_stdlib_imports}
{date_import}{_typing_imports}

{_base_import}

{_logging_init}


class {cls}({_base_class}):
    item = "{cls}"
    search_{nav}_url = "*/api/inventory_svc/{nav}/search?*"

    def create_{nav}(
        self,
        od_name: str,
        headers: Dict,
        {nav}_list: List[Dict],
        no_direct: bool = False,
        skip_create_if_exists: bool = False,
    ) -> None:
        """
        Create {cls} from a list of item dicts.

        Example data shape::

            {example_json}
        """
        for item in {nav}_list:
            if no_direct is False:
                self.direct_to_network_items("{nav}")

            need_create = True
            if skip_create_if_exists:
                if self.search_detail_ui_instead_oltp(
                    search_url=self.search_{nav}_url,
                    name=item.get("Name", item.get("Title1", "")),
                ):
                    {_logging_call}(f"Skipping — {entity} already exists: {{item.get('Name', item.get('Title1', ''))}}")
                    need_create = False

            if need_create:
                {_logging_call}(f"Creating {entity}: {{item}}")
                self.create_btn_click()
{full_body}{optional_block}
                self.wait_until_page_loaded()
                self.create_btn_click(wait_success=True)
                {_logging_call}(f"{entity} created successfully: {{item.get('Name', item.get('Title1', ''))}}")
'''


def _gen_data_json(s: _Script) -> str:
    """Generate {entity_plural}_Data.json content."""
    item_dict = {f.key: f.value for f in s.form_fields}
    data = {
        "MRM": [
            {
                "NetworkName": s.network_name,
                s.entity_plural: [item_dict],
            }
        ]
    }
    return json.dumps(data, indent=4)


def _gen_base_page_py() -> str:
    """Generate Base_page.py with common reusable method stubs."""
    return '''"""
Base page — common / reusable Playwright helper methods.

Generated by PRISM Shadow Coding enhancer.
Extend this class for all page objects.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from playwright.sync_api import BrowserContext, Page, expect

logger = logging.getLogger(__name__)


class BasePage:
    """Base class providing shared UI actions and login utilities."""

    def __init__(self, page: Page, context: Optional[BrowserContext] = None) -> None:
        self.page = page
        self.context = context

    # ── Login ──────────────────────────────────────────────────────────────────

    def mrm_login(self, network: str, username: str = "", password: str = "") -> None:
        """Log in to MRM for the given network.

        Credentials may be supplied directly or resolved from a secrets store.
        """
        logger.info(f"Logging in to MRM — network={network}")
        if self.context:
            self.context.clear_cookies()

        self.page.get_by_label("Login Name").fill(username)
        self.page.get_by_label("Password").fill(password)
        self.page.get_by_role("button", name="Log in").click()
        self.wait_until_page_loaded()

        # Extract network_id from URL if present
        m = re.search(r"/networks/(\d+)", self.page.url)
        if m:
            logger.debug(f"Network ID resolved from URL: {m.group(1)}")

    # ── Navigation ─────────────────────────────────────────────────────────────

    def direct_to_network_items(self, item_type: str) -> None:
        """Navigate to a Network Items sub-section (e.g. 'videos', 'audiences')."""
        logger.info(f"Navigating to Network Items → {item_type}")
        self.page.get_by_role("link", name="Network Items").click()
        self.page.get_by_role("link", name=item_type.capitalize()).click()
        self.wait_until_page_loaded()

    # ── CRUD helpers ───────────────────────────────────────────────────────────

    def create_btn_click(self, wait_success: bool = False) -> None:
        """Click the primary Create / Save button.

        Pass ``wait_success=True`` after the final form submission to also
        wait for the success notification to appear.
        """
        self.page.get_by_role("button", name=re.compile(r"Create|Save", re.IGNORECASE)).click()
        self.wait_until_page_loaded()
        if wait_success:
            self.wait_for_success_msg()

    def wait_until_page_loaded(self, timeout: float = 30_000) -> None:
        """Wait for the page network to be idle and any loading spinner to disappear."""
        self.page.wait_for_load_state("networkidle", timeout=timeout)

    def wait_for_success_msg(self, timeout: float = 15_000) -> None:
        """Assert that a success toast / alert becomes visible."""
        msg = self.page.locator("[role='alert'], .toast-success, .notification-success").first
        expect(msg).to_be_visible(timeout=timeout)
        logger.info("Success message confirmed.")

    # ── Relationship / Restriction helpers ─────────────────────────────────────

    def set_relationship(
        self,
        relationship_type: str,
        item_name: str,
        search_url: str = "",
    ) -> None:
        """Add a parent relationship (Series, Group, etc.) to the current item."""
        logger.info(f"Setting relationship '{relationship_type}' → {item_name}")
        self.page.get_by_role("button", name=relationship_type).click()
        self.page.get_by_role("textbox", name="Search").fill(item_name)
        if search_url:
            self.page.wait_for_response(lambda r: re.search(search_url, r.url) is not None)
        self.page.get_by_text(item_name, exact=True).first.click()
        self.page.get_by_role("button", name="Apply").click()
        self.wait_until_page_loaded()

    def set_restriction(self, restriction_data: Dict) -> None:
        """Apply distribution restrictions from a data dict."""
        logger.info(f"Setting restrictions: {restriction_data}")
        self.page.get_by_role("button", name="Restrictions").click()
        self.wait_until_page_loaded()
        # TODO: implement restriction field population based on restriction_data

    def search_detail_ui_instead_oltp(
        self,
        search_url: str,
        name: str,
    ) -> bool:
        """Search for an existing item via the UI search endpoint.

        Returns True if the item already exists (skip creation), False otherwise.
        """
        logger.info(f"Checking if item already exists: {name}")
        search_box = self.page.get_by_role("textbox", name="Search")
        if not search_box.is_visible():
            return False
        search_box.fill(name)
        with self.page.expect_response(
            lambda r: re.search(search_url, r.url) is not None,
            timeout=10_000,
        ) as resp_info:
            search_box.press("Enter")
        resp = resp_info.value
        try:
            data = resp.json()
            items = data.get("items") or data.get("results") or []
            return any(
                i.get("name", i.get("title", "")).lower() == name.lower()
                for i in items
            )
        except Exception:
            return False

    # ── Dropdown helpers ───────────────────────────────────────────────────────

    def select_from_dropdown_by_locator(self, locator: Any, value: str) -> None:
        """Select an option from a custom dropdown widget (not a native <select>)."""
        locator.click()
        self.page.get_by_role("option", name=value).click()
        self.wait_until_page_loaded()

    def select_from_circle_dropdown_no_test_id(self, label: str, value: str) -> None:
        """Select from a circle/pill-style dropdown identified by its visible label."""
        self.page.get_by_text(label, exact=True).click()
        self.page.get_by_role("option", name=value).click()
'''


# ── Extended generators (role-gated) ──────────────────────────────────────────

def _gen_locators_py(s: _Script) -> str:
    """Generate {entity}_Locators.py — centralised locator definitions (ui_locator role)."""
    prof = _role_profile("ui_locator")
    _imp = prof.get("imports", {})
    _header = "\n".join(_imp.get("header", ["from __future__ import annotations"]))
    _pw_api = prof.get("playwright", {}).get("locator_api", "get_by_role")

    cls = s.entity_plural

    locator_methods: List[str] = []
    for f in s.form_fields:
        method_name = re.sub(r"[\s\-]+", "_", f.key).lower()
        loc_expr = f.locator_code.replace("self.page", "self._page")
        locator_methods.append(
            f"    def {method_name}(self):\n"
            f"        return {loc_expr}"
        )

    locator_block = "\n\n".join(locator_methods) if locator_methods else (
        "    # TODO: add locator methods for this entity"
    )

    return f'''{_header}

from playwright.sync_api import Page


class {cls}Locators:
    """Centralised locator definitions for {cls}.

    Generated by PRISM Shadow Coding enhancer.
    Replace with real corporate locators as needed.
    """

    def __init__(self, page: Page) -> None:
        self._page = page

{locator_block}
'''


def _gen_controller_py(s: _Script) -> str:
    """Generate {entity}_Controller.py — orchestrator wiring page objects (controller role)."""
    prof = _role_profile("controller")
    _imp = prof.get("imports", {})
    _st  = prof.get("structure", {})
    _header      = "\n".join(_imp.get("header", ["from __future__ import annotations"]))
    _stdlib      = "\n".join(_imp.get("stdlib", ["import logging"]))
    _logging_init = _st.get("logging_init", "logger = logging.getLogger(__name__)")
    _logging_call = _st.get("logging_call", "logger.info")

    cls = s.entity_plural
    nav = s.nav_key

    has_locators = "ui_locator" in _active_roles()
    locator_import = f"from {cls}_Locators import {cls}Locators" if has_locators else ""
    locator_init   = f"        self.locators = {cls}Locators(page)" if has_locators else ""

    return f'''{_header}

{_stdlib}
from typing import Dict, List

import pytest
from playwright.sync_api import Page

from {cls}_UI import {cls}
{locator_import}

{_logging_init}


class {cls}Controller:
    """Controller that wires {cls} page object and locators for test use.

    Generated by PRISM Shadow Coding enhancer.
    """

    def __init__(self, page: Page) -> None:
        self.page     = page
        self.ui       = {cls}(page)
{locator_init}

    def create(self, od_name: str, headers: Dict, {nav}_list: List[Dict]) -> None:
        {_logging_call}(f"Controller: creating {cls} — {{len({nav}_list)}} item(s)")
        self.ui.create_{nav}(od_name, headers, {nav}_list)


@pytest.fixture
def {nav}_controller(page: Page) -> {cls}Controller:
    return {cls}Controller(page)
'''


def _gen_api_test_py(s: _Script) -> str:
    """Generate {entity}_test.py — API / integration test scaffold (api_test role)."""
    prof = _role_profile("api_test")
    _imp = prof.get("imports", {})
    _st  = prof.get("structure", {})
    _header      = "\n".join(_imp.get("header", ["from __future__ import annotations"]))
    _stdlib      = "\n".join(_imp.get("stdlib", ["import logging"]))
    _logging_init = _st.get("logging_init", "logger = logging.getLogger(__name__)")
    _logging_call = _st.get("logging_call", "logger.info")

    cls = s.entity_plural
    nav = s.nav_key

    return f'''{_header}

{_stdlib}

import httpx
import pytest

{_logging_init}


class Test{cls}Api:
    """{cls} API tests.

    Generated by PRISM Shadow Coding enhancer.
    Replace placeholder base_url and auth with project-specific config.
    """

    base_url: str = "{s.start_url or 'https://api.example.com'}"

    def test_create_{nav}(self) -> None:
        {_logging_call}("Testing POST /api/{nav}")
        payload = {{{", ".join(f'"{f.key}": "{f.value}"' for f in s.form_fields[:3])}}}
        response = httpx.post(f"{{self.base_url}}/api/{nav}", json=payload)
        assert response.status_code in (200, 201), response.text

    def test_get_{nav}(self) -> None:
        {_logging_call}("Testing GET /api/{nav}")
        response = httpx.get(f"{{self.base_url}}/api/{nav}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
'''


# ── Public API ─────────────────────────────────────────────────────────────────

class CodeEnhancer:
    """Transform raw playwright codegen output into three corporate-style files."""

    def __init__(
        self,
        session_id:   str = "shadow",
        network_name: str = "YourNetwork",
        output_dir:   Optional[str | Path] = None,
    ) -> None:
        self.session_id   = session_id
        self.network_name = network_name
        self.output_dir   = Path(output_dir) if output_dir else None

    # ── Main entry points ──────────────────────────────────────────────────────

    def enhance(self, raw_code: str) -> Dict[str, str]:
        """Parse raw codegen and return a dict of generated file contents.

        Core keys (always present):
            "ui"        — {entity}_UI.py content      (ui_action)
            "data"      — {entity}_Data.json content   (data_verify)
            "base_page" — Base_page.py content         (ui_page)
            "name"      — entity nav_key (e.g. 'videos')

        Extended keys (present only when the role has a by_role profile):
            "locators"   — {entity}_Locators.py        (ui_locator)
            "controller" — {entity}_Controller.py      (controller)
            "api_test"   — {entity}_test.py            (api_test)
        """
        lines  = _parse_raw(raw_code)
        script = _classify(lines)
        script.network_name = self.network_name
        active = _active_roles()

        result: Dict[str, str] = {
            "ui":        _gen_ui_py(script),
            "data":      _gen_data_json(script),
            "base_page": _gen_base_page_py(),
            "name":      script.nav_key,
        }
        if "ui_locator" in active:
            result["locators"] = _gen_locators_py(script)
        if "controller" in active:
            result["controller"] = _gen_controller_py(script)
        if "api_test" in active:
            result["api_test"] = _gen_api_test_py(script)
        return result

    def enhance_file(
        self,
        raw_path:   str | Path,
        output_dir: Optional[str | Path] = None,
    ) -> Dict[str, Path]:
        """Read raw codegen file and write output files for all active roles.

        Core files always written:
            ui        → {entity}_UI.py
            data      → {entity}_Data.json
            base_page → Base_page.py  (skipped if file already exists)

        Extended files (written only when the role has a by_role profile):
            locators   → {entity}_Locators.py
            controller → {entity}_Controller.py
            api_test   → {entity}_test.py

        Returns a dict of key → Path for every file written.
        """
        from Prism_view.shadow_coding.roles import output_path_for

        raw = Path(raw_path).read_text(encoding="utf-8")
        out = _choose_output_dir(raw_path, output_dir or self.output_dir)
        out.mkdir(parents=True, exist_ok=True)

        result  = self.enhance(raw)
        nav_key = result["name"]
        entity  = nav_key.capitalize()

        written: Dict[str, Path] = {}

        # Core files
        ui_path   = out / f"{nav_key}_UI.py"
        data_path = out / f"{nav_key}_Data.json"
        base_path = out / "Base_page.py"
        ui_path.write_text(result["ui"],    encoding="utf-8")
        data_path.write_text(result["data"], encoding="utf-8")
        written.update({"ui": ui_path, "data": data_path})
        if not base_path.exists():
            base_path.write_text(result["base_page"], encoding="utf-8")
        written["base_page"] = base_path

        # Extended files — use roles registry for consistent paths
        _ext_map = {
            "locators":   (f"{nav_key}_Locators.py",  "ui_locator"),
            "controller": (f"{nav_key}_Controller.py", "controller"),
            "api_test":   (f"{nav_key}_test.py",       "api_test"),
        }
        for key, (filename, role) in _ext_map.items():
            if key in result:
                ext_path = out / filename
                ext_path.write_text(result[key], encoding="utf-8")
                written[key] = ext_path

        return written


# ── Helpers ────────────────────────────────────────────────────────────────────

def _choose_output_dir(raw_path: str | Path, override: Optional[Path]) -> Path:
    if override:
        return Path(override)
    return Path(raw_path).parent
