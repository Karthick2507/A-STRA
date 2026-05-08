"""
Classify a single file into one of the 6 PRISM roles.

Supports:
  Code: .py  .ts  .js  .java
  Data: .xlsx  .pptx  .docx  .yaml  .yml  .json
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .scan_result import ScannedFile

# ──────────────────────────────────────────────────────────────────────────────
# Extension → language
# ──────────────────────────────────────────────────────────────────────────────

_EXT_LANG = {
    ".py":    "python",
    ".ts":    "typescript",
    ".js":    "javascript",
    ".java":  "java",
    ".xlsx":  "data",
    ".pptx":  "data",
    ".docx":  "data",
    ".yaml":  "data",
    ".yml":   "data",
    ".json":  "data",
}

# ──────────────────────────────────────────────────────────────────────────────
# Signal patterns
# ──────────────────────────────────────────────────────────────────────────────

# --- ui_page (BasePage) ---
_BASE_PAGE_PY  = [
    re.compile(r"class\s+\w+\s*\(\s*\w+\s*\)"),          # class Foo(Bar)
    re.compile(r"def\s+__init__\s*\(self.*page"),
    re.compile(r"self\._page\s*=|self\.page\s*="),
]
_BASE_PAGE_TS  = [
    re.compile(r"extends\s+\w+"),
    re.compile(r"constructor\s*\(.*Page"),
    re.compile(r"this\.page\s*="),
]
_BASE_PAGE_JAVA = [
    re.compile(r"class\s+\w+\s+extends\s+\w+"),
    re.compile(r"protected\s+Page\s+\w+"),
    re.compile(r"public\s+\w+\s*\(\s*Page\s"),
]

# --- ui_locator ---
_LOCATOR_PY   = [
    re.compile(r"get_by_role\(|get_by_text\(|get_by_label\(|get_by_placeholder\("),
    re.compile(r'By\.\w+\s*\(|xpath\s*=\s*["\']|css\s*=\s*["\']'),
    re.compile(r'data-testid|data-qa|aria-label'),
    re.compile(r'LOCATOR\s*=|SELECTOR\s*=|_loc\s*='),
]
_LOCATOR_TS   = [
    re.compile(r"getByRole\(|getByText\(|getByLabel\(|getByPlaceholder\("),
    re.compile(r"readonly\s+\w+\s*=\s*this\.page\.locator"),
    re.compile(r'data-testid|data-qa'),
]
_LOCATOR_JAVA = [
    re.compile(r"By\.xpath|By\.cssSelector|By\.id|By\.name"),
    re.compile(r"private\s+By\s+\w+"),
    re.compile(r'getByRole\(AriaRole|locator\s*\('),
]

# --- ui_action ---
_ACTION_PY   = [
    re.compile(r"\.click\(|\.fill\(|\.select_option\(|\.check\(|\.hover\("),
    re.compile(r"page\.goto\(|page\.navigate\(|page\.reload\("),
    re.compile(r"expect\(.*\)\.to_be_visible\(|assert.*is_visible"),
]
_ACTION_TS   = [
    re.compile(r"\.click\(\)|\.fill\(|\.selectOption\(|\.check\(|\.hover\("),
    re.compile(r"page\.goto\(|page\.navigate\(|page\.reload\("),
    re.compile(r"expect\(.*\)\.toBeVisible\(|toHaveText\("),
]
_ACTION_JAVA = [
    re.compile(r"\.click\(\)|\.sendKeys\(|\.selectByValue\("),
    re.compile(r"driver\.get\(|page\.navigate\("),
    re.compile(r"Assertions\.assert|assertEquals|assertTrue"),
]

# --- api_test ---
_APITEST_PY   = [
    re.compile(r"@pytest\.mark\.|def\s+test_\w+\s*\("),
    re.compile(r"assert\s+response\.|assert\s+status_code"),
    re.compile(r"requests\.get\(|requests\.post\(|httpx\."),
]
_APITEST_TS   = [
    re.compile(r"test\s*\(\s*['\"]|it\s*\(\s*['\"]|describe\s*\("),
    re.compile(r"expect\s*\(.*\)\.(toBe|toEqual|toContain)"),
    re.compile(r"fetch\s*\(|axios\.|supertest"),
]
_APITEST_JAVA = [
    re.compile(r"@Test|@BeforeEach|@AfterEach|@ParameterizedTest"),
    re.compile(r"assertEquals|assertThat|Assertions\."),
    re.compile(r"RestAssured\.|HttpClient\.|given\(\)\.when\("),
]

# --- controller ---
_CTRL_PY   = [
    re.compile(r"@pytest\.fixture"),
    re.compile(r"from\s+\S+\s+import\s+\w+Page\b"),
    re.compile(r"\w+_page\s*=\s*\w+Page\("),
]
_CTRL_TS   = [
    re.compile(r"import\s+.*Page.*from"),
    re.compile(r"const\s+\w+Page\s*=\s*new\s+\w+Page\("),
    re.compile(r"beforeAll\(|beforeEach\(|afterAll\("),
]
_CTRL_JAVA = [
    re.compile(r"@BeforeClass|@Before|@BeforeAll"),
    re.compile(r"new\s+\w+Page\s*\("),
    re.compile(r"private\s+\w+Page\s+\w+"),
]

# --- data_verify ---
_DATA_PY   = [
    re.compile(r"test_data\s*=\s*\{|DATA\s*=\s*\["),
    re.compile(r"@pytest\.mark\.parametrize"),
    re.compile(r"json\.load\(|yaml\.safe_load\("),
]
_DATA_TS   = [
    re.compile(r"const\s+\w+Data\s*=\s*\{|testData\s*="),
    re.compile(r"JSON\.parse\(|readFileSync\("),
]
_DATA_JAVA = [
    re.compile(r"@DataProvider|@CsvSource|@MethodSource"),
    re.compile(r"Map\.of\(|List\.of\(|new\s+HashMap"),
]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _count_hits(text: str, patterns: list) -> Tuple[int, List[str]]:
    hits, reasons = 0, []
    for p in patterns:
        m = p.search(text)
        if m:
            hits += 1
            reasons.append(m.group(0).strip()[:60])
    return hits, reasons


def _py_has_base_class(text: str) -> bool:
    try:
        tree = ast.parse(text)
        return any(
            isinstance(n, ast.ClassDef) and n.bases
            for n in ast.walk(tree)
        )
    except SyntaxError:
        return False


def _py_no_test_functions(text: str) -> bool:
    try:
        tree = ast.parse(text)
        return not any(
            isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
            for n in ast.walk(tree)
        )
    except SyntaxError:
        return True


# ──────────────────────────────────────────────────────────────────────────────
# Per-role scorers
# ──────────────────────────────────────────────────────────────────────────────

def _score(text: str, lang: str) -> dict[str, Tuple[float, List[str]]]:
    """Return {role: (raw_score, signals)} for all 6 roles."""
    scores: dict[str, Tuple[float, List[str]]] = {}

    pats_map = {
        "python":     (_BASE_PAGE_PY,  _LOCATOR_PY,  _ACTION_PY,  _APITEST_PY,  _DATA_PY,  _CTRL_PY),
        "typescript": (_BASE_PAGE_TS,  _LOCATOR_TS,  _ACTION_TS,  _APITEST_TS,  _DATA_TS,  _CTRL_TS),
        "javascript": (_BASE_PAGE_TS,  _LOCATOR_TS,  _ACTION_TS,  _APITEST_TS,  _DATA_TS,  _CTRL_TS),
        "java":       (_BASE_PAGE_JAVA,_LOCATOR_JAVA,_ACTION_JAVA,_APITEST_JAVA,_DATA_JAVA,_CTRL_JAVA),
    }
    role_keys = ["ui_page", "ui_locator", "ui_action", "api_test", "data_verify", "controller"]

    pats = pats_map.get(lang, (_BASE_PAGE_PY, _LOCATOR_PY, _ACTION_PY, _APITEST_PY, _DATA_PY, _CTRL_PY))
    for role, pat_group in zip(role_keys, pats):
        hits, reasons = _count_hits(text, pat_group)
        scores[role] = (hits, reasons)

    # Python AST bonuses
    if lang == "python":
        has_base = _py_has_base_class(text) and _py_no_test_functions(text)
        if has_base:
            old_hits, old_reasons = scores["ui_page"]
            scores["ui_page"] = (old_hits + 1.5, old_reasons + ["extends base class (AST)"])

    return scores


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def classify_file(path: Path) -> Optional[ScannedFile]:
    """Classify a single file. Returns None if extension is not supported."""
    lang = _EXT_LANG.get(path.suffix.lower())
    if lang is None:
        return None

    # Data files → always data_verify
    if lang == "data":
        return ScannedFile(
            path=path,
            language="data",
            role="data_verify",
            confidence=0.95,
            signals=[f"data file ({path.suffix})"],
        )

    text = _safe_read(path)
    if not text.strip():
        return None

    raw_scores = _score(text, lang)

    # Normalize to 0-1
    max_pats = 3  # each role group has 3 patterns; max possible raw score ≈ 3+1.5=4.5
    best_role, best_raw, best_signals = "ui_action", 0.0, []
    for role, (raw, signals) in raw_scores.items():
        if raw > best_raw:
            best_raw, best_role, best_signals = raw, role, signals

    # Confidence: cap at 0.97, floor at 0.30
    confidence = min(0.97, max(0.30, round(best_raw / max_pats, 2)))

    # If nothing scored, mark as low-confidence ui_action
    if best_raw == 0:
        return ScannedFile(
            path=path,
            language=lang,
            role="ui_action",
            confidence=0.30,
            signals=["no strong signals found"],
        )

    return ScannedFile(
        path=path,
        language=lang,
        role=best_role,
        confidence=confidence,
        signals=best_signals[:5],
    )
