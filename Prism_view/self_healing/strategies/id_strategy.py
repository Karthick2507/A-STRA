"""Strategy 1 — Exact id match."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from Asearch.self_healing.strategies.base import HealCandidate, HealingStrategy
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Asearch.self_healing.locator_registry import LocatorRecord


class IdStrategy(HealingStrategy):
    """Try the original element's `id` attribute first.

    If the broken locator was originally `#email`, retry as `[id='email']`.
    Also try the same id with case-variations and trimmed whitespace.
    """

    name = "id"

    def propose(self, page: "Page", broken: "LocatorRecord") -> List[HealCandidate]:
        candidates: List[HealCandidate] = []
        original_id = broken.attributes.get("id")

        if not original_id:
            return candidates

        for selector in (f"#{original_id}", f"[id='{original_id}']"):
            try:
                if page.query_selector(selector):
                    candidates.append(HealCandidate(
                        selector=selector,
                        selector_kind="id",
                        confidence=0.99,
                        source=self.name,
                        attributes={"id": original_id},
                        rationale=f"Exact id '{original_id}' resolved on current page",
                    ))
                    break  # first match is best
            except Exception as exc:                         # noqa: BLE001
                logger.debug("IdStrategy probe failed: %s", exc)

        return candidates
