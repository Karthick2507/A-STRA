"""
Strategy 5 — DOM neighbour / structural position.

Looks for an element near the same parent, sibling tag sequence, or with the
same nth-of-type position as the broken element. Useful when the target was
moved within its parent but otherwise unchanged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from Prism_view.self_healing.strategies.base import HealCandidate, HealingStrategy
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Prism_view.self_healing.locator_registry import LocatorRecord


class DomNeighbourStrategy(HealingStrategy):
    name = "dom"

    def propose(self, page: "Page", broken: "LocatorRecord") -> List[HealCandidate]:
        candidates: List[HealCandidate] = []
        neighbours = broken.neighbours or {}
        parent_sel  = neighbours.get("parent_selector")
        sibling_tag = neighbours.get("sibling_tag")
        nth         = neighbours.get("nth")
        own_tag     = (broken.attributes.get("tag") or "input").lower()

        if not parent_sel:
            return candidates

        try:
            parent = page.query_selector(parent_sel)
            if not parent:
                return candidates
        except Exception as exc:                             # noqa: BLE001
            logger.debug("DomNeighbourStrategy parent probe failed: %s", exc)
            return candidates

        # Try nth-of-type within parent
        if nth is not None:
            sel = f"{parent_sel} > {own_tag}:nth-of-type({nth + 1})"
            try:
                if page.query_selector(sel):
                    candidates.append(HealCandidate(
                        selector=sel,
                        selector_kind="css",
                        confidence=0.70,
                        source=self.name,
                        attributes={"tag": own_tag},
                        rationale=f"nth-of-type({nth + 1}) under {parent_sel}",
                    ))
            except Exception:                                # noqa: BLE001
                pass

        # Try sibling search (the element after a known-stable sibling)
        if sibling_tag:
            sel = f"{parent_sel} > {sibling_tag} ~ {own_tag}"
            try:
                if page.query_selector(sel):
                    candidates.append(HealCandidate(
                        selector=sel,
                        selector_kind="css",
                        confidence=0.65,
                        source=self.name,
                        attributes={"tag": own_tag, "sibling_tag": sibling_tag},
                        rationale=f"{own_tag} sibling-of-{sibling_tag} under {parent_sel}",
                    ))
            except Exception:                                # noqa: BLE001
                pass

        return candidates
