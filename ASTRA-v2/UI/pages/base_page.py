"""
ASTRA-v2 BasePage.

Every Page Object inherits from this class. It wraps Playwright's `Page` and
injects the self-healing pipeline transparently so that broken locators are
re-discovered at runtime without touching test code.

Key methods
───────────
  find(logical_name)         → Playwright Locator (self-healed if broken)
  click(logical_name)        → clicks the element (heals if broken)
  fill(logical_name, value)  → types into the element (heals if broken)
  select(logical_name, value)→ selects an <option> value
  get_text(logical_name)     → returns visible text
  is_visible(logical_name)   → bool

Locator registration
────────────────────
  Subclasses declare locators in `_LOCATORS`:

      _LOCATORS = {
          "login.email":    ("#email",    "id",   {"id": "email", "tag": "input"}),
          "login.password": ("#password", "id",   {"id": "password"}),
          "login.submit":   ("[type='submit']", "css", {"type": "submit", "tag": "button"}),
      }

  Each value is (selector, selector_kind, attributes_dict).
  Neighbours dict is optional as fourth element of the tuple.

  On first use the registry is initialised; on every use the active
  (possibly healed) selector is looked up.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from core.logging import logger
from core.config import CONFIG
from Asearch.self_healing.locator_registry import LocatorRecord, LocatorRegistry
from Asearch.self_healing.healer import HealerOrchestrator, HealingConfig

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator

# Registry shared across all pages in a test session (one per process)
_GLOBAL_REGISTRY: Optional[LocatorRegistry] = None

def _get_registry() -> LocatorRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = LocatorRegistry(
            CONFIG.paths.get("locator_registry_db", "Data/locators/locator_registry.db")
        )
    return _GLOBAL_REGISTRY


# ──────────────────────────────────────────────────────────────────────────────

class BasePage:
    """Base class for all ASTRA-v2 Page Objects."""

    # Subclasses override this dict.
    # Format: { logical_name: (selector, kind, attributes[, neighbours]) }
    _LOCATORS: Dict[str, Tuple] = {}

    def __init__(self, page: "Page") -> None:
        self.page      = page
        self._registry = _get_registry()
        self._healing_cfg = HealingConfig(
            enabled=CONFIG.self_healing.get("enabled", True),
            auto_apply_silent=CONFIG.self_healing.get("auto_apply_silent", True),
            min_confidence=CONFIG.self_healing.get("min_confidence", 0.75),
        )
        self._healer = HealerOrchestrator(self._registry, config=self._healing_cfg)
        self._register_locators()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register_locators(self) -> None:
        for logical_name, spec in self._LOCATORS.items():
            selector  = spec[0]
            kind      = spec[1]
            attrs     = spec[2] if len(spec) > 2 else {}
            neighbours = spec[3] if len(spec) > 3 else {}
            self._registry.upsert_initial(
                logical_name=logical_name,
                page_url=self.page.url or "",
                selector=selector,
                selector_kind=kind,
                attributes=attrs,
                neighbours=neighbours,
            )

    # ------------------------------------------------------------------
    # Core: find with self-healing
    # ------------------------------------------------------------------

    def find(self, logical_name: str) -> "Locator":
        """Return a Playwright Locator for the given logical name.

        If the active selector fails, the healing pipeline runs automatically.
        """
        record = self._get_active_record(logical_name)
        locator = self.page.locator(record.selector)

        # Fast path: selector resolves
        if self._is_present(record.selector):
            self._registry.record_success(record.id)
            return locator

        # Slow path: healing
        logger.heal(
            "Broken locator %r (%s) — starting heal", logical_name, record.selector
        )
        result = self._healer.heal(self.page, record)
        if result.success:
            return self.page.locator(result.selector)

        # Re-raise as a clear failure
        raise LocatorHealingError(
            f"Could not resolve or heal locator {logical_name!r} "
            f"(last selector={record.selector!r}). Reason: {result.reason}"
        )

    # ------------------------------------------------------------------
    # High-level actions
    # ------------------------------------------------------------------

    def click(self, logical_name: str, **kwargs: Any) -> None:
        self.find(logical_name).click(**kwargs)

    def fill(self, logical_name: str, value: str, **kwargs: Any) -> None:
        self.find(logical_name).fill(value, **kwargs)

    def select(self, logical_name: str, value: str) -> None:
        self.find(logical_name).select_option(value)

    def get_text(self, logical_name: str) -> str:
        return self.find(logical_name).inner_text()

    def is_visible(self, logical_name: str) -> bool:
        try:
            return self.find(logical_name).is_visible()
        except LocatorHealingError:
            return False

    def wait_for(
        self,
        logical_name: str,
        state: str = "visible",
        timeout: Optional[float] = None,
    ) -> "Locator":
        """Wait for the element to reach `state` ('visible', 'attached', 'hidden')."""
        opts: Dict[str, Any] = {"state": state}
        if timeout is not None:
            opts["timeout"] = timeout
        locator = self.find(logical_name)
        locator.wait_for(**opts)
        return locator

    def screenshot_on_failure(self, name: str = "failure") -> Optional[bytes]:
        try:
            ts = int(time.time())
            path = f"Data/screenshots/{name}_{ts}.png"
            return self.page.screenshot(path=path, full_page=True)
        except Exception:                                     # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_active_record(self, logical_name: str) -> LocatorRecord:
        record = self._registry.get_active(logical_name)
        if record is None:
            raise LocatorNotRegisteredError(
                f"{logical_name!r} is not registered in the locator registry. "
                f"Add it to the page's _LOCATORS dict."
            )
        return record

    def _is_present(self, selector: str) -> bool:
        try:
            return bool(self.page.query_selector(selector))
        except Exception:                                     # noqa: BLE001
            return False

    @property
    def url(self) -> str:
        return self.page.url

    def navigate(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")


# ──────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────────────────────────────────────

class LocatorHealingError(RuntimeError):
    """Raised when a broken locator cannot be healed within the configured threshold."""


class LocatorNotRegisteredError(KeyError):
    """Raised when a logical name is not present in the registry."""
