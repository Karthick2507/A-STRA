"""
PRISM API Base Client.

Wraps `httpx` with:
  - Pluggable auth adapters (Bearer, Basic, API-Key, Session Cookie, OAuth2)
  - Automatic retry via @retry decorator
  - Response logging at ASTRA's custom API log level
  - Allure attachment helper for API request/response evidence

Usage
─────
    client = APIClient(base_url="https://api.example.com", auth=BearerAuth("token"))
    resp   = client.get("/users/1")
    resp   = client.post("/users", json={"name": "Alice"})

All methods return an `httpx.Response`.  Raise on 4xx/5xx via
`resp.raise_for_status()` — the client does NOT raise automatically so
tests can assert on error responses.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import httpx

from core.logging import logger
from core.retry import retry, RetryError


class APIClient:
    """HTTP client with auth, retry, and structured logging."""

    DEFAULT_TIMEOUT = 30.0  # seconds

    def __init__(
        self,
        base_url:    str,
        auth=None,                    # Any auth adapter from auth_adapters.py
        timeout:     float = DEFAULT_TIMEOUT,
        headers:     Optional[Dict[str, str]] = None,
        verify_ssl:  bool = True,
    ) -> None:
        self.base_url   = base_url.rstrip("/")
        self._auth      = auth
        self._timeout   = timeout
        self._base_headers: Dict[str, str] = headers or {}
        self._verify_ssl = verify_ssl
        self._client: Optional[httpx.Client] = None

    # ------------------------------------------------------------------
    # Context manager / session lifecycle
    # ------------------------------------------------------------------

    def __enter__(self) -> "APIClient":
        self._client = self._build_client()
        return self

    def __exit__(self, *_: Any) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def _build_client(self) -> httpx.Client:
        auth_headers = self._auth.headers() if self._auth else {}
        merged = {**self._base_headers, **auth_headers}
        return httpx.Client(
            base_url=self.base_url,
            headers=merged,
            timeout=self._timeout,
            verify=self._verify_ssl,
        )

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    @retry(max_attempts=3, backoff=(2, 4, 8), exceptions=(httpx.TransportError,))
    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    @retry(max_attempts=3, backoff=(2, 4, 8), exceptions=(httpx.TransportError,))
    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("POST", path, **kwargs)

    @retry(max_attempts=3, backoff=(2, 4, 8), exceptions=(httpx.TransportError,))
    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("PUT", path, **kwargs)

    @retry(max_attempts=3, backoff=(2, 4, 8), exceptions=(httpx.TransportError,))
    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("PATCH", path, **kwargs)

    @retry(max_attempts=3, backoff=(2, 4, 8), exceptions=(httpx.TransportError,))
    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("DELETE", path, **kwargs)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        client = self._ensure_client()
        # Refresh auth headers (token may have rotated)
        if self._auth and hasattr(self._auth, "headers"):
            client.headers.update(self._auth.headers())

        t0 = time.perf_counter()
        try:
            resp = client.request(method, path, **kwargs)
        except httpx.TransportError as exc:
            logger.api("API %s %s → TRANSPORT ERROR: %s", method, path, exc)
            raise

        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        logger.api(
            "API %s %s → %d (%s) in %.0fms",
            method, path, resp.status_code, resp.reason_phrase, elapsed,
        )
        return resp

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def refresh_auth(self) -> None:
        """Force the auth adapter to re-acquire credentials."""
        if self._auth and hasattr(self._auth, "refresh"):
            self._auth.refresh()
        # Rebuild client so new headers take effect
        if self._client:
            self._client.close()
        self._client = self._build_client()

    def with_auth(self, auth: Any) -> "APIClient":
        """Return a copy of this client using a different auth adapter."""
        return APIClient(
            base_url=self.base_url,
            auth=auth,
            timeout=self._timeout,
            headers=dict(self._base_headers),
            verify_ssl=self._verify_ssl,
        )
