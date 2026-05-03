"""Strategy 2 — Exact name attribute match."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from Prism_view.self_healing.strategies.base import HealCandidate, HealingStrategy
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Prism_view.self_healing.locator_registry import LocatorRecord


class NameStrategy(HealingStrategy):
    """Retry with the original element's `name=` attribute."""

    name = "name"

    def propose(self, page: "Page", broken: "LocatorRecord") -> List[HealCandidate]:
        candidates: List[HealCandidate] = []
        attr_name = broken.attributes.get("name")

        if not attr_name:
            return candidates

        selector = f"[name='{attr_name}']"
        try:
            if page.query_selector(selector):
                candidates.append(HealCandidate(
                    selector=selector,
                    selector_kind="name",
                    confidence=0.95,
                    source=self.name,
                    attributes={"name": attr_name},
                    rationale=f"Exact name '{attr_name}' resolved on current page",
                ))
        except Exception as exc:                             # noqa: BLE001
            logger.debug("NameStrategy probe failed: %s", exc)

        return candidates
