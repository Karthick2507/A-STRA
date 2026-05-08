"""
Interactive CLI for reviewing a ScanResult before committing it to style_profile.json.

Top-level menu (per role group):
    [Y] Accept           → keep classification
    [N] Drop             → remove this role's files
    [R] Reassign         → move files to a different role
    [S] Skip             → don't change anything for this role

LOW-confidence assignments trigger a per-file prompt.
"""
from __future__ import annotations

from typing import Optional

from .scan_report import format_report, format_role_detail
from .scan_result import RoleAssignment, ScanResult

_VALID_ROLES = ["ui_page", "ui_action", "ui_locator", "controller", "api_test", "data_verify"]


def _prompt(msg: str, valid: list[str], default: Optional[str] = None) -> str:
    valid_lower = [v.lower() for v in valid]
    suffix = "/".join(v.upper() if v.lower() == (default or "").lower() else v for v in valid)
    while True:
        try:
            ans = input(f"{msg} [{suffix}]: ").strip().lower()
        except EOFError:
            return default or valid[0]
        if not ans and default:
            return default.lower()
        if ans in valid_lower:
            return ans
        print(f"  Please answer one of: {', '.join(valid)}")


def _reassign_role(current: str) -> str:
    print(f"  Reassign from '{current}'. Available roles:")
    for i, r in enumerate(_VALID_ROLES, 1):
        print(f"    {i}. {r}")
    while True:
        try:
            ans = input("  New role number (or 'cancel'): ").strip().lower()
        except EOFError:
            return current
        if ans == "cancel":
            return current
        if ans.isdigit() and 1 <= int(ans) <= len(_VALID_ROLES):
            return _VALID_ROLES[int(ans) - 1]
        print("  Invalid choice.")


def _review_low_confidence(assignment: RoleAssignment) -> RoleAssignment:
    """Per-file Y/R/N prompt for LOW-confidence assignments."""
    print(f"\n  ⚠ LOW confidence on '{assignment.role}' — reviewing each file:")
    keep = []
    for sf in assignment.files:
        print(f"\n    {sf.path}")
        print(f"      confidence : {sf.confidence:.2f}")
        print(f"      signals    : {', '.join(sf.signals) or '(none)'}")
        ans = _prompt("    Keep as " + assignment.role + "?", ["y", "n", "r"], default="y")
        if ans == "y":
            keep.append(sf)
        elif ans == "r":
            new_role = _reassign_role(assignment.role)
            sf.role = new_role
            keep.append(sf)
        # 'n' → drop this file
    assignment.files = keep
    return assignment


def review_scan(result: ScanResult, *, non_interactive: bool = False) -> ScanResult:
    """Walk the user through each role assignment and let them adjust.

    Returns the (possibly mutated) ScanResult.
    In *non_interactive* mode, all assignments are auto-accepted.
    """
    print(format_report(result))
    if non_interactive:
        return result

    print("\nReview each role: [Y]es accept, [N]o drop, [R]eassign, [S]kip\n")

    new_assignments: dict[str, RoleAssignment] = {}
    for role, assignment in list(result.assignments.items()):
        print(format_role_detail(result, role))
        ans = _prompt(f"\nAction for '{role}'?", ["y", "n", "r", "s"], default="y")

        if ans == "n":
            continue  # drop entirely
        if ans == "s":
            new_assignments[role] = assignment
            continue
        if ans == "r":
            new_role = _reassign_role(role)
            for f in assignment.files:
                f.role = new_role
            new_assignments.setdefault(new_role, RoleAssignment(role=new_role)).files.extend(assignment.files)
            continue

        # 'y' — accepted, but if LOW confidence, drill down
        if assignment.confidence_level == "LOW":
            assignment = _review_low_confidence(assignment)
        if assignment.files:
            new_assignments[role] = assignment

    result.assignments = new_assignments
    print("\n✓ Review complete.")
    print(format_report(result))
    return result
