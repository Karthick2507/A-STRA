"""Pretty text reports for ScanResult."""
from __future__ import annotations

from .scan_result import ScanResult

_SEP = "─" * 78


def format_report(result: ScanResult) -> str:
    lines = []
    lines.append(_SEP)
    lines.append(f"PRISM folder scan — {result.root}")
    lines.append(_SEP)
    lines.append(f"  Files scanned    : {result.total_files_scanned}")
    lines.append(f"  Languages found  : {', '.join(result.languages_found) or '(none)'}")
    lines.append(f"  Roles assigned   : {len(result.assignments)}")
    lines.append(f"  Unclassified     : {len(result.unclassified)}")
    lines.append("")
    lines.append(f"  {'Role':<14} {'Conf':<8} {'Files':<6}  Examples")
    lines.append(f"  {'-'*14} {'-'*8} {'-'*6}  {'-'*40}")

    for role in ["ui_page", "ui_action", "ui_locator", "controller", "api_test", "data_verify"]:
        a = result.assignments.get(role)
        if not a:
            lines.append(f"  {role:<14} {'—':<8} {'0':<6}  (not detected)")
            continue
        examples = ", ".join(f.path.name for f in a.files[:3])
        if len(a.files) > 3:
            examples += f", … (+{len(a.files) - 3})"
        lines.append(
            f"  {role:<14} {a.confidence_level:<8} {len(a.files):<6}  {examples}"
        )

    lines.append(_SEP)
    return "\n".join(lines)


def format_role_detail(result: ScanResult, role: str) -> str:
    a = result.assignments.get(role)
    if not a:
        return f"No files assigned to '{role}'."
    out = [f"Role '{role}' — {len(a.files)} file(s), {a.confidence_level} confidence"]
    for f in a.files:
        out.append(f"  [{f.confidence:.2f}] {f.path}")
        for s in f.signals:
            out.append(f"          ↳ {s}")
    return "\n".join(out)
