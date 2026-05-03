"""
PRISM Retry Handler.

Decorator-based retry with exponential backoff. Used by:
    - API client (transient HTTP errors)
    - Self-healing strategies (race conditions on DOM updates)
    - Network webhook posts (Slack/Teams 5xx)

Example:

    @retry(max_attempts=3, backoff=[2, 4, 8])
    def fetch_users():
        return httpx.get("/api/users").raise_for_status().json()
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable, Iterable, Tuple, Type, TypeVar

from core.logging import logger

F = TypeVar("F", bound=Callable[..., Any])


class RetryError(RuntimeError):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, attempts: int, last_exc: BaseException) -> None:
        self.attempts = attempts
        self.last_exc = last_exc
        super().__init__(f"Exhausted {attempts} retry attempts. Last: {last_exc!r}")


def retry(
    max_attempts: int = 3,
    backoff: Iterable[float] = (2, 4, 8),
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_giveup: Callable[[BaseException], None] | None = None,
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff.

    Args:
        max_attempts: Total attempts including the first.
        backoff: Per-attempt sleep schedule (seconds). Cycles if shorter than max_attempts.
        exceptions: Tuple of exception types that trigger a retry.
        on_giveup: Optional hook called with the last exception before raising RetryError.
    """
    backoff_list = list(backoff) or [1]

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    sleep_for = backoff_list[(attempt - 1) % len(backoff_list)]
                    logger.warning(
                        "Retry %s/%s for %s after %.1fs (%s: %s)",
                        attempt, max_attempts, fn.__qualname__,
                        sleep_for, type(exc).__name__, exc,
                    )
                    time.sleep(sleep_for)

            if on_giveup and last_exc:
                try:
                    on_giveup(last_exc)
                except Exception:  # noqa: BLE001
                    pass
            assert last_exc is not None
            raise RetryError(max_attempts, last_exc) from last_exc

        return wrapper  # type: ignore[return-value]

    return decorator
