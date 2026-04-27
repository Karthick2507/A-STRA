"""ASTRA bearer token extraction analyser - intercepts API responses for auth tokens."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from playwright.sync_api import Page, Response
from utils.env_loader import ENV, update_env_file
from utils.logger import logger


class BearerTokenAnalyser:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.token: Optional[str] = None
        self.source: Optional[str] = None

    def analyse(self) -> Dict[str, Any]:
        logger.preflight("BearerTokenAnalyser: intercepting network traffic...")

        # Listen for all responses
        def handle_response(response: Response) -> None:
            try:
                if response.status == 200 or response.status == 201:
                    body = response.text()
                    token = self._extract_from_body(body)
                    if token and self._validate_token(token):
                        self.token = token
                        self.source = "response_body"
                        logger.preflight(f"  Token extracted from {response.url}")
            except Exception:
                pass

        self.page.on("response", handle_response)
        return {"token": self.token, "source": self.source, "status": "PASS" if self.token else "SKIP"}

    def _extract_from_body(self, body: str) -> Optional[str]:
        try:
            data = json.loads(body)
            return self._search_object(data, ["token", "access_token", "jwt", "Bearer"])
        except Exception:
            return None

    def _search_object(self, obj: Any, keys: list[str]) -> Optional[str]:
        if isinstance(obj, dict):
            for key in keys:
                if key in obj:
                    val = obj[key]
                    if isinstance(val, str) and len(val) > 10:
                        return val
            for value in obj.values():
                result = self._search_object(value, keys)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._search_object(item, keys)
                if result:
                    return result
        return None

    def _validate_token(self, token: str) -> bool:
        if not token or len(token) < 10:
            return False
        # Try to make a request with the token
        endpoints = ["/api/me", "/api/profile", "/api/user", "/api/whoami"]
        for ep in endpoints:
            try:
                response = self.page.request.get(
                    f"{ENV.BASE_URL}{ep}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if response.status < 400:
                    self.source = "token_validated"
                    return True
            except Exception:
                continue
        return False

    def save_token(self) -> None:
        if self.token:
            update_env_file("BEARER_TOKEN", self.token)
            logger.preflight(f"  Token saved to .env")
