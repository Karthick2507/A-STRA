"""
PRISM WebSocket Client.

Thin wrapper around `websockets` (sync via `websockets.sync.client`) for
testing WebSocket endpoints.  Falls back to a stub if `websockets` is not
installed so the rest of the framework remains importable.

Usage
─────
    with WebSocketClient("wss://api.example.com/ws") as ws:
        ws.send({"action": "subscribe", "channel": "prices"})
        msg = ws.receive(timeout=5.0)
        assert msg["event"] == "snapshot"

The client converts dict payloads to JSON automatically.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, List, Optional, Union

from core.logging import logger

try:
    from websockets.sync.client import connect as ws_connect  # type: ignore
    _WS_OK = True
except ImportError:                                           # pragma: no cover
    _WS_OK = False


class WebSocketClient:
    """Sync WebSocket client for API tests."""

    def __init__(
        self,
        url:      str,
        headers:  Optional[dict] = None,
        timeout:  float = 10.0,
    ) -> None:
        if not _WS_OK:
            raise ImportError(
                "websockets not installed. Run: pip install websockets"
            )
        self.url      = url
        self._headers = headers or {}
        self._timeout = timeout
        self._conn    = None
        self._messages: List[Any] = []
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "WebSocketClient":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def connect(self) -> None:
        self._conn = ws_connect(self.url, additional_headers=self._headers)
        logger.api("WebSocket connected to %s", self.url)

    def close(self) -> None:
        self._stop_event.set()
        if self._conn:
            try:
                self._conn.close()
            except Exception:                                # noqa: BLE001
                pass
            self._conn = None
        logger.api("WebSocket closed")

    # ------------------------------------------------------------------
    # Send / receive
    # ------------------------------------------------------------------

    def send(self, payload: Union[str, dict, bytes]) -> None:
        if self._conn is None:
            raise RuntimeError("WebSocket not connected. Use as a context manager.")
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        self._conn.send(payload)
        logger.api("WS → sent: %s", str(payload)[:120])

    def receive(self, timeout: Optional[float] = None) -> Any:
        """Receive one message (blocks up to `timeout` seconds)."""
        if self._conn is None:
            raise RuntimeError("WebSocket not connected.")
        t = timeout if timeout is not None else self._timeout
        self._conn.socket.settimeout(t)
        raw = self._conn.recv()
        logger.api("WS ← recv: %s", str(raw)[:120])
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    def receive_all(self, count: int, timeout: float = 10.0) -> List[Any]:
        """Collect exactly `count` messages within `timeout` seconds."""
        messages: List[Any] = []
        deadline = time.time() + timeout
        while len(messages) < count and time.time() < deadline:
            remaining = deadline - time.time()
            try:
                msg = self.receive(timeout=max(0.1, remaining))
                messages.append(msg)
            except Exception:                                # noqa: BLE001
                break
        return messages

    # ------------------------------------------------------------------
    # Background listener
    # ------------------------------------------------------------------

    def start_listener(self, callback: Callable[[Any], None]) -> None:
        """Start a background thread that calls `callback` for every message."""
        if self._listener_thread and self._listener_thread.is_alive():
            return
        self._stop_event.clear()

        def _listen() -> None:
            while not self._stop_event.is_set():
                try:
                    msg = self.receive(timeout=1.0)
                    self._messages.append(msg)
                    callback(msg)
                except Exception:                            # noqa: BLE001
                    if self._stop_event.is_set():
                        break

        self._listener_thread = threading.Thread(target=_listen, daemon=True)
        self._listener_thread.start()

    def stop_listener(self) -> None:
        self._stop_event.set()

    @property
    def collected_messages(self) -> List[Any]:
        return list(self._messages)
