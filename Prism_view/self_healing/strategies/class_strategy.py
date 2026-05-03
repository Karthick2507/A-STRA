"""
Strategy 4 — CSS class similarity (Jaccard).

Scores DOM elements whose class set overlaps with the broken locator's
original class list. Jaccard = |A ∩ B| / |A ∪ B|.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Set

from Prism_view.self_healing.strategies.base import HealCandidate, HealingStrategy
from core.logging import logger

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Prism_view.self_healing.locator_registry import LocatorRecord


def _to_set(value: str | None) -> Set[str]:
    if not value:
        return set()
    return {tok for tok in value.split() if tok}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    return len(inter) / len(union) if union else 0.0


class ClassStrategy(HealingStrategy):
    name = "class"
    THRESHOLD = 0.50

    def propose(self, page: "Page", broken: "LocatorRecord") -> List[HealCandidate]:
        candidates: List[HealCandidate] = []
        target_classes = _to_set(broken.attributes.get("class"))
        if not target_classes:
            return candidates

        same_tag = broken.attributes.get("tag", "").lower() or "*"
        try:
            elements = page.query_selector_all(same_tag if same_tag != "*" else "*")
        except Exception as exc:                             # noqa: BLE001
            logger.debug("ClassStrategy DOM scan failed: %s", exc)
            return candidates

        for el in elements:
            try:
                cls = el.get_attribute("class")
                el_classes = _to_set(cls)
                if not el_classes:
                    continue
                score = _jaccard(target_classes, el_classes)
                if score < self.THRESHOLD:
                    continue

                # Compose a CSS selector using top 2 most distinctive shared classes
                shared = sorted(target_classes & el_classes)[:2]
                if not shared:
                    continue
                sel = (same_tag if same_tag != "*" else "") + "".join(f".{c}" for c in shared)

                candidates.append(HealCandidate(
                    selector=sel,
                    selector_kind="css",
                    confidence=round(score * 0.85, 3),
                    source=self.name,
                    attributes={"class": cls, "tag": same_tag},
                    rationale=f"jaccard={score:.2f} on classes {shared}",
                ))
            except Exception:                                # noqa: BLE001
                continue

        candidates.sort()
        return candidates[:5]
