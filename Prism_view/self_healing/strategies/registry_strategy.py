"""
Strategy 6 — Historical locator registry lookup.

Retries any prior known-good selectors for this logical_name. Useful when the
DOM has reverted or when an A/B test variant restored an older form.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from Prism_view.self_healing.strategies.base import HealCandidate, HealingStrategy
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Prism_view.self_healing.locator_registry import LocatorRecord, LocatorRegistry


class RegistryStrategy(HealingStrategy):
    name = "registry"

    def __init__(self, registry: "LocatorRegistry") -> None:
        self.registry = registry

    def propose(self, page: "Page", broken: "LocatorRecord") -> List[HealCandidate]:
        candidates: List[HealCandidate] = []
        history = self.registry.get_history(broken.logical_name, limit=10)

        for past in history:
            if past.id == broken.id:
                continue                                     # skip the current broken one
            try:
                if page.query_selector(past.selector):
                    # Confidence boosted by past success_count (capped at +0.20)
                    boost = min(0.20, 0.02 * past.success_count)
                    confidence = round(0.55 + boost, 3)
                    candidates.append(HealCandidate(
                        selector=past.selector,
                        selector_kind=past.selector_kind,
                        confidence=confidence,
                        source=self.name,
                        attributes=past.attributes,
                        rationale=f"historic variant id={past.id} success={past.success_count}",
                    ))
            except Exception as exc:                         # noqa: BLE001
                logger.debug("RegistryStrategy probe failed: %s", exc)

        candidates.sort()
        return candidates[:3]
