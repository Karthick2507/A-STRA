"""
ASTRA-v2 healing strategy base class + shared types.

Every strategy implements:
    propose(page, broken_record) -> List[HealCandidate]

The healer iterates strategies in priority order and stops at the first
candidate whose confidence meets the configured threshold.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Asearch.self_healing.locator_registry import LocatorRecord


@dataclass
class HealCandidate:
    """A proposed locator that *might* be the new home of a broken element."""
    selector:      str
    selector_kind: str                                # id | name | aria | css | xpath | text
    confidence:    float                              # 0..1
    source:        str                                # name of the strategy that produced it
    attributes:    Dict[str, Any] = field(default_factory=dict)
    rationale:     str            = ""

    def __lt__(self, other: "HealCandidate") -> bool:
        # higher confidence ranks first
        return self.confidence > other.confidence


class HealingStrategy(ABC):
    """Abstract base for a single healing strategy."""

    name: str = "base"

    @abstractmethod
    def propose(
        self,
        page: "Page",
        broken: "LocatorRecord",
    ) -> List[HealCandidate]:
        """Return zero or more candidates ordered by confidence (best first)."""
        ...
