"""
Strategy 3 — aria-label / placeholder text similarity.

Uses normalised string ratio (Python stdlib `difflib.SequenceMatcher`) to find
elements whose aria-label or placeholder text closely matches the original
element's value. No external NLP dependency, runs CPU-only.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING, List

from Prism_view.self_healing.strategies.base import HealCandidate, HealingStrategy
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Prism_view.self_healing.locator_registry import LocatorRecord


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


class AriaStrategy(HealingStrategy):
    """Score every element on the page by aria-label / placeholder similarity."""

    name = "aria"
    SIMILARITY_THRESHOLD = 0.80

    def propose(self, page: "Page", broken: "LocatorRecord") -> List[HealCandidate]:
        candidates: List[HealCandidate] = []
        target_aria        = broken.attributes.get("aria-label", "") or ""
        target_placeholder = broken.attributes.get("placeholder", "") or ""
        target_label       = broken.attributes.get("label",       "") or ""
        target = target_aria or target_placeholder or target_label

        if not target:
            return candidates

        try:
            elements = page.query_selector_all(
                "input, select, textarea, button, [aria-label], [placeholder]"
            )
        except Exception as exc:                             # noqa: BLE001
            logger.debug("AriaStrategy DOM scan failed: %s", exc)
            return candidates

        for el in elements:
            try:
                aria        = el.get_attribute("aria-label") or ""
                placeholder = el.get_attribute("placeholder") or ""
                el_id       = el.get_attribute("id")
                el_name     = el.get_attribute("name")

                score = max(_ratio(target, aria), _ratio(target, placeholder))
                if score < self.SIMILARITY_THRESHOLD:
                    continue

                # Build the most stable selector for this candidate
                if el_id:
                    sel, kind = f"#{el_id}", "id"
                elif el_name:
                    sel, kind = f"[name='{el_name}']", "name"
                elif aria:
                    sel, kind = f"[aria-label='{aria}']", "aria"
                elif placeholder:
                    sel, kind = f"[placeholder='{placeholder}']", "css"
                else:
                    continue

                candidates.append(HealCandidate(
                    selector=sel,
                    selector_kind=kind,
                    confidence=round(score * 0.95, 3),       # cap at 0.95 — never beat exact id
                    source=self.name,
                    attributes={"aria-label": aria, "placeholder": placeholder,
                                "id": el_id, "name": el_name},
                    rationale=f"aria/placeholder ratio={score:.2f} vs '{target}'",
                ))
            except Exception:                                # noqa: BLE001
                continue

        candidates.sort()                                    # HealCandidate.__lt__ → highest conf first
        return candidates[:5]
