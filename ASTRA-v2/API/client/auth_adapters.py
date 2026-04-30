"""
ASTRA-v2 API Auth Adapters.

Each adapter exposes `.headers() → dict` so APIClient can inject them into
every request.  Adapters that manage tokens also expose `.refresh()`.

Supported auth types
────────────────────
  BearerAuth      — Authorization: Bearer <token>
  BasicAuth       — Authorization: Basic <base64(user:pass)>
  ApiKeyAuth      — X-Api-Key: <key>  (or custom header name)
  SessionCookieAuth — Cookie: <name>=<value>  (session token)
  OAuth2ClientCredentials — auto-acquires + renews access token via /token endpoint
"""
from __future__ import annotations

import base64
import time
from typing import Any, Dict, Optional

import httpx

from core.logging import logger


# ──────────────────────────────────────────────────────────────────────────────
# Bearer Token
# ──────────────────────────────────────────────────────────────────────────────

class BearerAuth:
    """Static Bearer token (no refresh)."""

    def __init__(self, token: str) -> None:
        self._token = token

    def headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def set_token(self, token: str) -> None:
        self._token = token


# ──────────────────────────────────────────────────────────────────────────────
# Basic Auth
# ──────────────────────────────────────────────────────────────────────────────

class BasicAuth:
    """HTTP Basic authentication (RFC 7617)."""

    def __init__(self, username: str, password: str) -> None:
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self._header = f"Basic {encoded}"

    def headers(self) -> Dict[str, str]:
        return {"Authorization": self._header}


# ──────────────────────────────────────────────────────────────────────────────
# API Key
# ──────────────────────────────────────────────────────────────────────────────

class ApiKeyAuth:
    """API key passed as a header (default: X-Api-Key) or query param."""

    def __init__(
        self,
        api_key:     str,
        header_name: str = "X-Api-Key",
        query_param: Optional[str] = None,
    ) -> None:
        self._key         = api_key
        self._header_name = header_name
        self._query_param = query_param

    def headers(self) -> Dict[str, str]:
        if self._query_param:
            return {}                       # key goes into query string instead
        return {self._header_name: self._key}

    def query_params(self) -> Dict[str, str]:
        if self._query_param:
            return {self._query_param: self._key}
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Session Cookie
# ──────────────────────────────────────────────────────────────────────────────

class SessionCookieAuth:
    """Authenticate via a session cookie (e.g. connect.sid, JSESSIONID)."""

    def __init__(self, cookie_name: str, cookie_value: str) -> None:
        self._name  = cookie_name
        self._value = cookie_value

    def headers(self) -> Dict[str, str]:
        return {"Cookie": f"{self._name}={self._value}"}

    def set_cookie(self, value: str) -> None:
        self._value = value


# ──────────────────────────────────────────────────────────────────────────────
# OAuth2 Client Credentials
# ──────────────────────────────────────────────────────────────────────────────

class OAuth2ClientCredentials:
    """
    OAuth2 client_credentials flow.

    Automatically fetches an access token on first use and refreshes it
    when it is within `refresh_buffer_secs` of expiry.

    Args:
        token_url:          Full URL of the /token endpoint
        client_id:          OAuth2 client_id
        client_secret:      OAuth2 client_secret
        scope:              Space-separated scopes (optional)
        refresh_buffer_secs: Refresh token this many seconds before expiry (default 30)
    """

    def __init__(
        self,
        token_url:           str,
        client_id:           str,
        client_secret:       str,
        scope:               Optional[str] = None,
        refresh_buffer_secs: int = 30,
    ) -> None:
        self._token_url    = token_url
        self._client_id    = client_id
        self._client_secret = client_secret
        self._scope        = scope
        self._buffer       = refresh_buffer_secs
        self._token:        Optional[str] = None
        self._expires_at:   float = 0.0

    def headers(self) -> Dict[str, str]:
        if self._needs_refresh():
            self.refresh()
        return {"Authorization": f"Bearer {self._token}"}

    def refresh(self) -> None:
        payload: Dict[str, Any] = {
            "grant_type":    "client_credentials",
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
        }
        if self._scope:
            payload["scope"] = self._scope

        try:
            resp = httpx.post(self._token_url, data=payload, timeout=15)
            resp.raise_for_status()
            data            = resp.json()
            self._token     = data["access_token"]
            expires_in      = int(data.get("expires_in", 3600))
            self._expires_at = time.time() + expires_in
            logger.api(
                "OAuth2 token acquired (expires_in=%ds, scope=%s)",
                expires_in, data.get("scope", self._scope),
            )
        except Exception as exc:                             # noqa: BLE001
            logger.error("OAuth2 token fetch failed: %s", exc)
            raise

    def _needs_refresh(self) -> bool:
        return self._token is None or time.time() >= (self._expires_at - self._buffer)
