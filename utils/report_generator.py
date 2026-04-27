"""ASTRA report generator - builds HTML + JSON preflight reports."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import logger

_REPORTS_DIR = Path(__file__).parent.parent / "reports"


@dataclass
class AnalyserResult:
    name: str
    status: str  # 'PASS' | 'WARN' | 'FAIL' | 'SKIP'
    duration_ms: float
    findings: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PreflightReport:
    run_id: str
    timestamp: str
    overall_status: str  # 'PASS' | 'WARN' | 'FAIL'
    total_duration_ms: float
    environment: str
    base_url: str
    analysers: List[AnalyserResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def build_report(
    run_id: str,
    base_url: str,
    environment: str,
    analysers: List[AnalyserResult],
    total_duration_ms: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> PreflightReport:
    statuses = {r.status for r in analysers}
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    return PreflightReport(
        run_id=run_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        overall_status=overall,
        total_duration_ms=total_duration_ms,
        environment=environment,
        base_url=base_url,
        analysers=analysers,
        metadata=metadata or {},
    )


def generate_reports(report: PreflightReport) -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    save_json_report(report)
    save_html_report(report)
    logger.preflight(f"Reports saved to {_REPORTS_DIR}")


def save_json_report(report: PreflightReport) -> Path:
    path = _REPORTS_DIR / f"preflight_{report.run_id}.json"
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path


def save_html_report(report: PreflightReport) -> Path:
    path = _REPORTS_DIR / f"preflight_{report.run_id}.html"
    path.write_text(_render_html(report), encoding="utf-8")
    return path


def _status_color(status: str) -> str:
    return {"PASS": "#4caf50", "WARN": "#ff9800", "FAIL": "#f44336", "SKIP": "#9e9e9e"}.get(
        status, "#9e9e9e"
    )


def _render_html(report: PreflightReport) -> str:
    rows = ""
    for r in report.analysers:
        color = _status_color(r.status)
        warnings_html = ""
        if r.warnings:
            warnings_html = "<br><small style='color:#ff9800'>" + "; ".join(r.warnings) + "</small>"
        errors_html = ""
        if r.errors:
            errors_html = "<br><small style='color:#f44336'>" + "; ".join(r.errors) + "</small>"
        rows += f"""
        <tr>
          <td>{r.name}</td>
          <td style='color:{color};font-weight:bold'>{r.status}</td>
          <td>{r.duration_ms:.0f} ms</td>
          <td>{warnings_html}{errors_html}</td>
        </tr>"""

    overall_color = _status_color(report.overall_status)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ASTRA Preflight Report</title>
  <style>
    body {{ background:#121212; color:#e0e0e0; font-family:monospace; padding:2rem; }}
    h1 {{ color:#bb86fc; }}
    h2 {{ color:#03dac6; }}
    table {{ width:100%; border-collapse:collapse; margin-top:1rem; }}
    th {{ background:#1e1e1e; color:#bb86fc; padding:.5rem 1rem; text-align:left; }}
    td {{ padding:.5rem 1rem; border-bottom:1px solid #333; }}
    .badge {{ display:inline-block; padding:.2rem .6rem; border-radius:4px;
              font-weight:bold; color:#000; background:{overall_color}; }}
    .meta {{ color:#9e9e9e; font-size:.85rem; margin-bottom:1rem; }}
  </style>
</head>
<body>
  <h1>ASTRA Preflight Report</h1>
  <p class="meta">
    Run ID: {report.run_id} &nbsp;|
    {report.timestamp} &nbsp;|
    {report.environment} &nbsp;|
    {report.base_url}
  </p>
  <p>Overall status: <span class="badge">{report.overall_status}</span>
     &nbsp; Total duration: {report.total_duration_ms:.0f} ms</p>
  <h2>Analyser Results</h2>
  <table>
    <thead><tr><th>Analyser</th><th>Status</th><th>Duration</th><th>Notes</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""
