"""
ASTRA-v2 Test Result Notifiers.

Send a run summary to Slack, Microsoft Teams, or Email when tests finish.
All channels are optional — configured via config.json / .env.

Each notifier exposes `.send(report: RunReport)`.  The dispatcher
`notify_all(report)` sends to every configured channel.

Config keys (config.json or .env)
──────────────────────────────────
  SLACK_WEBHOOK_URL        — incoming webhook URL
  TEAMS_WEBHOOK_URL        — MS Teams connector webhook URL
  NOTIFY_EMAIL_TO          — comma-separated recipient addresses
  NOTIFY_EMAIL_FROM        — sender address
  NOTIFY_EMAIL_SMTP_HOST   — SMTP host (default: localhost)
  NOTIFY_EMAIL_SMTP_PORT   — SMTP port (default: 587)
  NOTIFY_EMAIL_USERNAME    — SMTP auth user (optional)
  NOTIFY_EMAIL_PASSWORD    — SMTP auth password (optional)
"""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import httpx

from core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Report data model
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RunReport:
    total:    int
    passed:   int
    failed:   int
    skipped:  int
    duration: float           # seconds
    env:      str = "dev"
    branch:   str = ""
    job_url:  str = ""        # CI job URL
    failures: List[str] = field(default_factory=list)  # first N failure names

    @property
    def status(self) -> str:
        return "PASSED" if self.failed == 0 else "FAILED"

    @property
    def pass_rate(self) -> str:
        if self.total == 0:
            return "N/A"
        return f"{self.passed / self.total * 100:.1f}%"

    def summary_text(self) -> str:
        lines = [
            f"ASTRA Test Run — {self.status}",
            f"Env: {self.env}  Branch: {self.branch or 'unknown'}",
            f"Total: {self.total}  Passed: {self.passed}  "
            f"Failed: {self.failed}  Skipped: {self.skipped}",
            f"Pass rate: {self.pass_rate}  Duration: {self.duration:.1f}s",
        ]
        if self.failures:
            lines.append("Failures:")
            for name in self.failures[:5]:
                lines.append(f"  • {name}")
        if self.job_url:
            lines.append(f"Report: {self.job_url}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Slack
# ──────────────────────────────────────────────────────────────────────────────

class SlackNotifier:
    """Send test result summary to a Slack incoming webhook."""

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")

    def send(self, report: RunReport) -> bool:
        if not self.webhook_url:
            logger.debug("SlackNotifier: no webhook URL configured")
            return False
        emoji = ":white_check_mark:" if report.failed == 0 else ":x:"
        color = "good" if report.failed == 0 else "danger"
        payload: Dict[str, Any] = {
            "attachments": [{
                "color": color,
                "title": f"{emoji} ASTRA — {report.status} ({report.env})",
                "text":  report.summary_text(),
                "footer": "ASTRA-v2",
            }]
        }
        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Slack notification sent")
                return True
            logger.warning("Slack webhook returned %d: %s", resp.status_code, resp.text[:200])
        except Exception as exc:                             # noqa: BLE001
            logger.warning("Slack notification failed: %s", exc)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Microsoft Teams
# ──────────────────────────────────────────────────────────────────────────────

class TeamsNotifier:
    """Send test result summary to a Microsoft Teams webhook (Adaptive Card)."""

    def __init__(self, webhook_url: Optional[str] = None) -> None:
        self.webhook_url = webhook_url or os.getenv("TEAMS_WEBHOOK_URL", "")

    def send(self, report: RunReport) -> bool:
        if not self.webhook_url:
            logger.debug("TeamsNotifier: no webhook URL configured")
            return False
        color = "00cc00" if report.failed == 0 else "cc0000"
        card: Dict[str, Any] = {
            "@type":      "MessageCard",
            "@context":   "http://schema.org/extensions",
            "themeColor": color,
            "summary":    f"ASTRA — {report.status}",
            "sections": [{
                "activityTitle": f"ASTRA Test Run — {report.status}",
                "activityText":  report.summary_text(),
            }],
        }
        if report.job_url:
            card["potentialAction"] = [{
                "@type": "OpenUri",
                "name":  "View Report",
                "targets": [{"os": "default", "uri": report.job_url}],
            }]
        try:
            resp = httpx.post(self.webhook_url, json=card, timeout=10)
            if resp.status_code == 200:
                logger.info("Teams notification sent")
                return True
            logger.warning("Teams webhook returned %d: %s", resp.status_code, resp.text[:200])
        except Exception as exc:                             # noqa: BLE001
            logger.warning("Teams notification failed: %s", exc)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Email
# ──────────────────────────────────────────────────────────────────────────────

class EmailNotifier:
    """Send test result summary via SMTP."""

    def __init__(
        self,
        to:        Optional[str] = None,
        from_addr: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username:  Optional[str] = None,
        password:  Optional[str] = None,
    ) -> None:
        self.to        = to        or os.getenv("NOTIFY_EMAIL_TO", "")
        self.from_addr = from_addr or os.getenv("NOTIFY_EMAIL_FROM", "astra@example.com")
        self.smtp_host = smtp_host or os.getenv("NOTIFY_EMAIL_SMTP_HOST", "localhost")
        self.smtp_port = smtp_port or int(os.getenv("NOTIFY_EMAIL_SMTP_PORT", "587"))
        self.username  = username  or os.getenv("NOTIFY_EMAIL_USERNAME", "")
        self.password  = password  or os.getenv("NOTIFY_EMAIL_PASSWORD", "")

    def send(self, report: RunReport) -> bool:
        if not self.to:
            logger.debug("EmailNotifier: no recipient configured")
            return False

        subject = f"[ASTRA] {report.status} — {report.env} — {report.pass_rate} pass rate"
        body    = report.summary_text()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self.from_addr
        msg["To"]      = self.to
        msg.attach(MIMEText(body, "plain"))
        # Simple HTML version
        html_body = "<pre>" + body.replace("&", "&amp;").replace("<", "&lt;") + "</pre>"
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as smtp:
                smtp.ehlo()
                if self.smtp_port == 587:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.sendmail(self.from_addr, self.to.split(","), msg.as_string())
            logger.info("Email notification sent to %s", self.to)
            return True
        except Exception as exc:                             # noqa: BLE001
            logger.warning("Email notification failed: %s", exc)
            return False


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────────

def notify_all(report: RunReport) -> Dict[str, bool]:
    """Fire all configured notifiers. Returns dict of channel → success."""
    results: Dict[str, bool] = {}
    for name, notifier in [
        ("slack",  SlackNotifier()),
        ("teams",  TeamsNotifier()),
        ("email",  EmailNotifier()),
    ]:
        results[name] = notifier.send(report)
    return results
