"""
ASTRA-v2 A* Search Node.

A Node represents a discrete state in the application's UI graph.

State dimensions
────────────────
    page_url         URL after the most recent navigation (normalised)
    tab_index        Active browser tab/frame index (0-based)
    filled_fields    Frozenset of (logical_name, value) tuples — tracks form progress
    popup_state      Describes any currently open dialog: None | "alert" | "confirm"
                     | "modal:<title>" | "prompt"
    path             Ordered sequence of actions that produced this state (for replay)

Why frozenset for filled_fields?
  Equality and hashing require an immutable, order-independent structure. Two
  nodes that have the same fields filled in different order are the same state.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Tuple


def _normalise_url(url: str) -> str:
    """Strip trailing slash, fragment, and common tracking params."""
    url = url.split("#")[0].rstrip("/")
    # Remove utm_* and fbclid params
    url = re.sub(r"[&?](utm_\w+|fbclid)=[^&]*", "", url)
    return url


@dataclass(frozen=True)
class AStarNode:
    """Immutable search node for the A* form-completion engine."""

    page_url:      str
    tab_index:     int                        = 0
    filled_fields: FrozenSet[Tuple[str, str]] = field(default_factory=frozenset)
    popup_state:   Optional[str]              = None

    # g = cost from start; h = heuristic estimate to goal
    # These are NOT part of the node identity (frozen fields are for hashing)
    # They are stored as mutable attributes on wrapper objects in the priority queue.

    def with_field(self, name: str, value: str) -> "AStarNode":
        return AStarNode(
            page_url=self.page_url,
            tab_index=self.tab_index,
            filled_fields=self.filled_fields | frozenset({(name, value)}),
            popup_state=self.popup_state,
        )

    def with_url(self, url: str) -> "AStarNode":
        return AStarNode(
            page_url=_normalise_url(url),
            tab_index=self.tab_index,
            filled_fields=self.filled_fields,
            popup_state=self.popup_state,
        )

    def with_popup(self, state: Optional[str]) -> "AStarNode":
        return AStarNode(
            page_url=self.page_url,
            tab_index=self.tab_index,
            filled_fields=self.filled_fields,
            popup_state=state,
        )

    @classmethod
    def from_page(cls, url: str, tab_index: int = 0) -> "AStarNode":
        return cls(page_url=_normalise_url(url), tab_index=tab_index)

    def __repr__(self) -> str:
        fields = f"|{len(self.filled_fields)} filled" if self.filled_fields else ""
        popup  = f"|popup={self.popup_state}" if self.popup_state else ""
        return f"Node({self.page_url!r}{fields}{popup})"


@dataclass
class AStarNodeEntry:
    """Priority-queue entry wrapping a node with cost/heuristic scores."""

    node:    AStarNode
    g:       float = 0.0           # actual cost from start
    h:       float = 0.0           # heuristic estimate to goal
    parent:  Optional["AStarNodeEntry"] = None
    action:  Optional[str] = None  # the action taken to reach this node

    @property
    def f(self) -> float:
        return self.g + self.h

    def __lt__(self, other: "AStarNodeEntry") -> bool:
        return self.f < other.f

    def reconstruct_path(self) -> List[str]:
        """Return ordered list of actions from start to this node."""
        actions: List[str] = []
        entry: Optional[AStarNodeEntry] = self
        while entry is not None and entry.action is not None:
            actions.append(entry.action)
            entry = entry.parent
        actions.reverse()
        return actions
