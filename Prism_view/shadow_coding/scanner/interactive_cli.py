"""
Interactive CLI for prism learn --scan.

New flow (v2):
  1. Show scan summary (files found).
  2. Ask user to define their File Control Flow Hierarchy
     (the types of files their framework uses, e.g. Data.yaml, Action.py, …).
  3. Confirm hierarchy with Y/N.
  4. For each hierarchy entry:
       a. Auto-suggest a PRISM role based on the name; user can override.
       b. List every file in the scanned folder and let user pick by number
          (comma-separated multi-select, e.g.  1,3,4).
  5. Build a new ScanResult from the user's selections.
  6. Persist via SlateLearner.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .scan_report import format_report
from .scan_result import RoleAssignment, ScanResult, ScannedFile
from .file_classifier import _EXT_LANG

_VALID_ROLES = [
    "ui_page",
    "ui_action",
    "ui_locator",
    "controller",
    "api_test",
    "data_verify",
]

_ROLE_DESCRIPTIONS = {
    "ui_page":     "Base page class / shared helper methods",
    "ui_action":   "Page object actions (.click, .fill, .goto, …)",
    "ui_locator":  "Static selectors / locator constants",
    "controller":  "Orchestrator that wires page objects together",
    "api_test":    "Test file (@pytest.mark / @Test / def test_…)",
    "data_verify": "Test data / fixtures (.yaml / .json / .xlsx / …)",
}

# ── Role auto-suggest from type label ─────────────────────────────────────────

_KEYWORDS: List[Tuple[List[str], str]] = [
    (["data",  "yaml",  "json",  "fixture", "xlsx", "pptx", "docx"], "data_verify"),
    (["test",  "spec",  "it_"],                                       "api_test"),
    (["action"],                                                       "ui_action"),
    (["locator", "selector", "by_"],                                   "ui_locator"),
    (["controller", "orchestrat", "fixture", "setup"],                 "controller"),
    (["base"],                                                         "ui_page"),
    (["page",  "ui_"],                                                 "ui_page"),
]


def _suggest_role(label: str) -> str:
    lower = label.lower()
    for keywords, role in _KEYWORDS:
        if any(kw in lower for kw in keywords):
            return role
    return "ui_action"


# ── Low-level input helpers ────────────────────────────────────────────────────

def _ask(prompt: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default or ""
    return ans if ans else (default or "")


def _ask_yes_no(prompt: str, default: str = "y") -> bool:
    opts = "Y/n" if default == "y" else "y/N"
    ans = _ask(f"{prompt} [{opts}]", default).lower()
    return ans in ("y", "yes")


def _pick_role(current_suggestion: str) -> str:
    print()
    print("  Map to PRISM role:")
    for i, role in enumerate(_VALID_ROLES, 1):
        marker = " ← recommended" if role == current_suggestion else ""
        print(f"    {i}. {role:<16} {_ROLE_DESCRIPTIONS[role]}{marker}")
    while True:
        ans = _ask(f"  Role number", str(_VALID_ROLES.index(current_suggestion) + 1))
        if ans.isdigit() and 1 <= int(ans) <= len(_VALID_ROLES):
            return _VALID_ROLES[int(ans) - 1]
        print("  Invalid. Enter a number from the list.")


def _pick_files(
    all_files: List[Path],
    role: str,
    type_label: str,
) -> List[Path]:
    """Show numbered file list; return the subset chosen by the user."""
    print()
    print(f"  Select files for  '{type_label}'  →  role: {role}")
    print(f"  (comma-separated numbers, e.g.  1,3   or just  2)")
    print()
    for i, f in enumerate(all_files, 1):
        print(f"    {i:3}. {f.name}")
    print()
    while True:
        raw = _ask("  Your selection (or Enter to skip)").strip()
        if not raw:
            return []
        parts = re.split(r"[,\s]+", raw)
        chosen: List[Path] = []
        bad = []
        for p in parts:
            if p.isdigit() and 1 <= int(p) <= len(all_files):
                chosen.append(all_files[int(p) - 1])
            else:
                bad.append(p)
        if bad:
            print(f"  Ignored invalid entries: {bad}")
        if chosen:
            return chosen
        return []


# ── Public entry point ─────────────────────────────────────────────────────────

def review_scan(result: ScanResult, *, non_interactive: bool = False) -> ScanResult:
    """Walk the user through hierarchy-first file classification.

    In *non_interactive* mode (--yes flag), auto-accepts the automatic
    classification without prompting.
    """
    print(format_report(result))

    if non_interactive:
        return result

    # ── Collect all files from the scanned folder ──────────────────────────
    all_files = _collect_all_files(result.root)
    if not all_files:
        print("No supported files found in the folder.")
        return result

    # ── Step 1: Define hierarchy ───────────────────────────────────────────
    print()
    print("─" * 78)
    print("  STEP 1 — Define your File Control Flow Hierarchy")
    print("─" * 78)
    print("  Tell PRISM the types of files your framework uses.")
    print("  Enter one type per line (use a descriptive label).")
    print("  Examples:  Data.yaml   Action.py   UI_Page.py   Test.py   Base_page.py")
    print("  Press Enter on an empty line when done.")
    print()

    hierarchy: List[str] = []
    index = 1
    while True:
        label = _ask(f"  File type {index}").strip()
        if not label:
            if index == 1:
                print("  At least one file type is required.")
                continue
            break
        hierarchy.append(label)
        index += 1

    # ── Confirm hierarchy ──────────────────────────────────────────────────
    print()
    print("  Your File Control Flow Hierarchy:")
    for i, label in enumerate(hierarchy, 1):
        suggested = _suggest_role(label)
        print(f"    {i}. {label:<30}  → auto-role: {suggested}")
    print()
    if not _ask_yes_no("  Continue with this hierarchy?"):
        print("  Aborted — no changes made.")
        return ScanResult(root=result.root)

    # ── Step 2: Role + file selection per hierarchy entry ─────────────────
    print()
    print("─" * 78)
    print("  STEP 2 — Map file types to PRISM roles and select matching files")
    print("─" * 78)

    new_assignments: Dict[str, RoleAssignment] = {}

    for i, label in enumerate(hierarchy, 1):
        print()
        print(f"  ── [{i}/{len(hierarchy)}] File type: {label} ──")

        suggested_role = _suggest_role(label)
        chosen_role = _pick_role(suggested_role)

        chosen_paths = _pick_files(all_files, chosen_role, label)
        if not chosen_paths:
            print(f"  Skipped — no files assigned for '{label}'.")
            continue

        lang = _detect_lang(chosen_paths)

        if chosen_role not in new_assignments:
            new_assignments[chosen_role] = RoleAssignment(role=chosen_role)

        for path in chosen_paths:
            file_lang = _EXT_LANG.get(path.suffix.lower(), "python")
            new_assignments[chosen_role].files.append(
                ScannedFile(
                    path=path,
                    language=file_lang,
                    role=chosen_role,
                    confidence=0.95,
                    signals=[f"user-selected for '{label}'"],
                )
            )
        print(f"  ✓ {len(chosen_paths)} file(s) → {chosen_role}")

    # ── Rebuild result ─────────────────────────────────────────────────────
    all_langs = sorted({
        sf.language
        for a in new_assignments.values()
        for sf in a.files
        if sf.language != "data"
    })

    result.assignments    = new_assignments
    result.languages_found = all_langs
    result.unclassified   = []

    print()
    print("✓ Hierarchy complete.")
    print(format_report(result))
    return result


# ── Helpers ────────────────────────────────────────────────────────────────────

def _collect_all_files(root: Path) -> List[Path]:
    """Return every supported file under *root*, sorted by name."""
    from .folder_scanner import _DEFAULT_IGNORE, _SUPPORTED_EXTS
    files: List[Path] = []
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        if any(part in _DEFAULT_IGNORE for part in entry.parts):
            continue
        if entry.suffix.lower() in _SUPPORTED_EXTS:
            files.append(entry)
    return files


def _detect_lang(paths: List[Path]) -> str:
    if not paths:
        return "python"
    lang = _EXT_LANG.get(paths[0].suffix.lower(), "python")
    return lang
