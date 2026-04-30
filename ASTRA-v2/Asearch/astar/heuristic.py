"""
ASTRA-v2 A* Heuristic h(n).

h(n) estimates the remaining cost from state n to the goal.

Goal definition
───────────────
The goal is reached when the page matches at least one configured success
signal:
    - URL pattern match (glob or regex)
    - Visible text pattern match (title, heading, or body)
    - DOM element presence (CSS selector)

Cost model
──────────
Each action has cost 1.0 by default. Heuristic under-estimates cost to
keep A* admissible (never over-estimates = guaranteed optimal path).

Heuristic breakdown
───────────────────
  H_url:    0.0 if goal URL matches, else 1.0 (at minimum one navigation away)
  H_fields: number of fields not yet filled (lower bound on fill actions needed)
  H_popup:  0.5 if a blocking popup is open (must dismiss before continuing)

Total h(n) = H_url + H_fields + H_popup
"""
from __future__ import annotations

import re
from fnmatch import fnmatch
from typing import List, Optional

from Asearch.astar.node import AStarNode


class GoalSpec:
    """Encodes what 'success' looks like for a given automation goal."""

    def __init__(
        self,
        url_patterns:     Optional[List[str]] = None,
        text_patterns:    Optional[List[str]] = None,
        element_selectors: Optional[List[str]] = None,
        required_fields:   Optional[List[str]] = None,
    ) -> None:
        self.url_patterns      = url_patterns      or []
        self.text_patterns     = text_patterns      or []
        self.element_selectors = element_selectors  or []
        self.required_fields   = required_fields    or []

    def url_matches(self, url: str) -> bool:
        if not self.url_patterns:
            return False
        for pattern in self.url_patterns:
            if pattern.startswith("re:"):
                if re.search(pattern[3:], url):
                    return True
            elif fnmatch(url, pattern):
                return True
        return False

    def fields_remaining(self, filled_fields: frozenset) -> int:
        filled_names = {name for name, _ in filled_fields}
        return sum(1 for f in self.required_fields if f not in filled_names)


class AStarHeuristic:
    """Compute h(n) for a node given a goal specification."""

    def __init__(self, goal: GoalSpec) -> None:
        self.goal = goal

    def __call__(self, node: AStarNode) -> float:
        return self.estimate(node)

    def estimate(self, node: AStarNode) -> float:
        h = 0.0

        # URL proximity
        if self.goal.url_patterns and not self.goal.url_matches(node.page_url):
            h += 1.0

        # Unfilled required fields
        h += float(self.goal.fields_remaining(node.filled_fields))

        # Blocking popup penalty
        if node.popup_state is not None:
            h += 0.5

        return h

    def is_goal_url(self, url: str) -> bool:
        return self.goal.url_matches(url) if self.goal.url_patterns else False
