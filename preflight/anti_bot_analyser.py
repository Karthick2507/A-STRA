"""ASTRA anti-bot detection analyser - detects CAPTCHA, Cloudflare, WAF, rate limits, etc."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from playwright.sync_api import Page
from utils.logger import logger


@dataclass
class AntiBotFinding:
    threat_type: str
    threat_level: str  # NONE, LOW, MEDIUM, HIGH
    description: str
    detected_at: Optional[str] = None


@dataclass
class AntiBotAnalyserResult:
    overall_threat_level: str
    findings: List[AntiBotFinding] = field(default_factory=list)
    is_testable: bool = True
    recommendation: str = ""


class AntiBotAnalyser:
    def __init__(self, page: Page) -> None:
        self.page = page

    def analyse(self) -> AntiBotAnalyserResult:
        findings: List[AntiBotFinding] = []

        # Check 1: CAPTCHA detection
        if self._detect_captcha():
            findings.append(AntiBotFinding(
                threat_type="CAPTCHA",
                threat_level="HIGH",
                description="reCAPTCHA, hCaptcha, or similar CAPTCHA detected",
            ))

        # Check 2: Cloudflare detection
        if self._detect_cloudflare():
            findings.append(AntiBotFinding(
                threat_type="Cloudflare",
                threat_level="MEDIUM",
                description="Cloudflare protection or challenge detected",
            ))

        # Check 3: WAF detection
        if self._detect_waf():
            findings.append(AntiBotFinding(
                threat_type="WAF",
                threat_level="MEDIUM",
                description="Web Application Firewall (WAF) detected",
            ))

        # Check 4: Rate limiting
        if self._detect_rate_limit():
            findings.append(AntiBotFinding(
                threat_type="Rate Limiting",
                threat_level="LOW",
                description="Rate limiting or throttling signals detected",
            ))

        # Check 5: Honeypot fields
        if self._detect_honeypot():
            findings.append(AntiBotFinding(
                threat_type="Honeypot Fields",
                threat_level="LOW",
                description="Honeypot form fields (hidden anti-bot fields) detected",
            ))

        # Check 6: Bot detection scripts
        if self._detect_bot_scripts():
            findings.append(AntiBotFinding(
                threat_type="Bot Detection Scripts",
                threat_level="MEDIUM",
                description="JavaScript bot detection/challenge scripts detected",
            ))

        # Check 7: Headless detection
        if self._is_headless_detectable():
            findings.append(AntiBotFinding(
                threat_type="Headless Detection",
                threat_level="LOW",
                description="Page may detect headless browser mode",
            ))

        # Compute overall threat level
        levels = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
        max_level_num = max([levels.get(f.threat_level, 0) for f in findings] + [0])
        level_map = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "NONE"}
        overall = level_map[max_level_num]

        return AntiBotAnalyserResult(
            overall_threat_level=overall,
            findings=findings,
            is_testable=overall in ["NONE", "LOW"],
            recommendation=self._get_recommendation(overall, findings),
        )

    def _detect_captcha(self) -> bool:
        captcha_indicators = [
            'recaptcha', 'hcaptcha', 'captcha', 'challenge',
            '[data-sitekey]', '.g-recaptcha', '.h-captcha',
        ]
        for indicator in captcha_indicators:
            if self.page.query_selector(indicator) or indicator in self.page.content():
                return True
        return False

    def _detect_cloudflare(self) -> bool:
        cf_indicators = ['__cfruid', 'challenge-form', 'cf_clearance']
        content = self.page.content()
        for indicator in cf_indicators:
            if indicator in content:
                return True
        try:
            cookies = self.page.context.cookies()
            return any(c['name'] == 'cf_clearance' for c in cookies)
        except Exception:
            return False

    def _detect_waf(self) -> bool:
        waf_indicators = ['ModSecurity', 'WAF', 'AWS WAF', 'Imperva', 'F5']
        content = self.page.content()
        headers = {}
        try:
            headers = dict(self.page.evaluate('() => Object.fromEntries(new Headers(fetch.headers).entries())'))
        except Exception:
            pass
        waf_headers = ['X-ModSecurity', 'X-WAF-ID', 'Server']
        return any(ind in content for ind in waf_indicators) or any(
            h in headers for h in waf_headers
        )

    def _detect_rate_limit(self) -> bool:
        rate_limit_indicators = ['rate limit', 'Too many requests', '429', 'try again later', 'throttle']
        return any(ind in self.page.content() for ind in rate_limit_indicators)

    def _detect_honeypot(self) -> bool:
        honeypot_fields = self.page.query_selector_all(
            'input[style*="display:none"], input[hidden], input[type=hidden][name*="phone"]'
        )
        return len(honeypot_fields) > 0

    def _detect_bot_scripts(self) -> bool:
        bot_script_indicators = ['_phantom', '__webdriver', 'webdriver', 'chrome.webstore']
        content = self.page.content()
        return any(ind in content for ind in bot_script_indicators)

    def _is_headless_detectable(self) -> bool:
        headless_checks = [
            'navigator.webdriver',
            'phantom',
            '__nightmare',
            'nightmareState',
        ]
        content = self.page.content()
        return any(check in content for check in headless_checks)

    def _get_recommendation(self, threat_level: str, findings: List[AntiBotFinding]) -> str:
        if threat_level == "HIGH":
            return "Manual testing or special handling required. Automation may be blocked."
        elif threat_level == "MEDIUM":
            return "Proceed with caution. Consider adding delays and realistic user-agent patterns."
        elif threat_level == "LOW":
            return "Automation should work. Minor anti-bot measures detected."
        return "No significant anti-bot protection detected."
