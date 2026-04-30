"""
ASTRA-v2 A* Search Engine.

The engine drives a live Playwright browser through a web application,
treating each UI state as a graph node and each UI action as an edge with
cost 1.0.  It uses A* (f = g + h) to find the shortest path from the
initial page load to the goal state.

Goal detection
──────────────
  1. URL matches a GoalSpec.url_patterns entry
  2. A success text/element is visible on the page
  3. All required fields have been filled (for form-completion tasks)

Integration with self-healing
─────────────────────────────
  When an action fails because a locator is broken, the engine delegates to
  HealerOrchestrator. If healing succeeds, the action is retried with the new
  selector before counting as a failure.

Algorithm
─────────
  Standard A* with a dict-based open set (priority queue) and a closed set.
  Nodes are AStarNode instances (frozen dataclasses — hashable).
  f(n) = g(n) + h(n), where h is the AStarHeuristic.
"""
from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from core.logging import logger
from core.config import CONFIG
from Asearch.astar.node import AStarNode, AStarNodeEntry, _normalise_url
from Asearch.astar.heuristic import AStarHeuristic, GoalSpec
from Asearch.astar.graph_builder import Action, GraphBuilder

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from Asearch.self_healing.healer import HealerOrchestrator


# ──────────────────────────────────────────────────────────────────────────────
# Result
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AStarResult:
    success:       bool
    path:          List[str]           = field(default_factory=list)   # action descriptions
    nodes_visited: int                 = 0
    elapsed_ms:    float               = 0.0
    final_url:     str                 = ""
    reason:        str                 = ""

    def __repr__(self) -> str:
        if self.success:
            return (
                f"AStarResult(ok, {len(self.path)} steps, "
                f"{self.nodes_visited} nodes, {self.elapsed_ms:.0f}ms)"
            )
        return f"AStarResult(FAIL: {self.reason})"


# ──────────────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────────────

class AStarEngine:
    """Drive a Playwright page via A* to reach a goal state."""

    def __init__(
        self,
        page:    "Page",
        goal:    GoalSpec,
        healer:  Optional["HealerOrchestrator"] = None,
        data_path: str = "Data/UI",
        max_iterations: int = 0,
        heuristic_weight: float = 0.0,
    ) -> None:
        self.page    = page
        self.goal    = goal
        self.healer  = healer
        self._h      = AStarHeuristic(goal)
        self._builder = GraphBuilder(data_path)
        self._max_iter = max_iterations or CONFIG.astar_max_iterations
        self._w        = heuristic_weight or CONFIG.astar_heuristic_weight

    def search(self, start_url: Optional[str] = None) -> AStarResult:
        """Run A* from current page (or `start_url` if given)."""
        t0 = time.perf_counter()

        if start_url:
            self.page.goto(start_url, wait_until="domcontentloaded")

        start_node = AStarNode.from_page(self.page.url)
        start_entry = AStarNodeEntry(
            node=start_node,
            g=0.0,
            h=self._w * self._h.estimate(start_node),
        )

        # open_set: min-heap of (f, entry)
        open_set: List[tuple] = []
        heapq.heappush(open_set, (start_entry.f, start_entry))
        # best_g: node → lowest g seen
        best_g: Dict[AStarNode, float] = {start_node: 0.0}
        closed: Set[AStarNode] = set()
        iterations = 0

        logger.astar(
            "A* search started from %s toward %s",
            start_node.page_url, self.goal.url_patterns,
        )

        while open_set and iterations < self._max_iter:
            iterations += 1
            _, current = heapq.heappop(open_set)

            if current.node in closed:
                continue
            closed.add(current.node)

            # Sync browser to this node's state (nav + fill replay)
            if not self._restore_state(current):
                continue

            # Goal check
            if self._is_goal():
                logger.astar(
                    "Goal reached after %d iterations, %d nodes visited",
                    iterations, len(closed),
                )
                return AStarResult(
                    success=True,
                    path=current.reconstruct_path(),
                    nodes_visited=len(closed),
                    elapsed_ms=_ms(t0),
                    final_url=self.page.url,
                )

            # Expand successors
            actions = self._builder.successors(self.page, current.node.filled_fields)
            for action in actions:
                next_node, action_desc = self._apply_action(current.node, action)
                if next_node is None:
                    continue
                if next_node in closed:
                    continue

                new_g = current.g + action.cost
                if new_g >= best_g.get(next_node, float("inf")):
                    continue

                best_g[next_node] = new_g
                next_entry = AStarNodeEntry(
                    node=next_node,
                    g=new_g,
                    h=self._w * self._h.estimate(next_node),
                    parent=current,
                    action=action_desc,
                )
                heapq.heappush(open_set, (next_entry.f, next_entry))

        reason = (
            f"max iterations ({self._max_iter}) reached"
            if iterations >= self._max_iter
            else "open set exhausted"
        )
        logger.astar("A* failed after %d iterations: %s", iterations, reason)
        return AStarResult(
            success=False,
            nodes_visited=len(closed),
            elapsed_ms=_ms(t0),
            final_url=self.page.url,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _restore_state(self, entry: AStarNodeEntry) -> bool:
        """Navigate page to match entry.node.page_url if needed."""
        current_url = _normalise_url(self.page.url)
        if current_url != entry.node.page_url:
            try:
                self.page.goto(entry.node.page_url, wait_until="domcontentloaded")
            except Exception as exc:                         # noqa: BLE001
                logger.debug("A* state restore nav failed: %s", exc)
                return False
        return True

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _apply_action(
        self, node: AStarNode, action: Action
    ) -> tuple[Optional[AStarNode], str]:
        """Execute `action` on the browser and return (new_node, description)."""
        try:
            if action.kind == "fill":
                self.page.locator(action.selector).fill(action.value)
                new_node = node.with_field(action.logical_name, action.value)
                desc = f"fill({action.logical_name!r}, {action.value!r})"

            elif action.kind == "click":
                self.page.locator(action.selector).click()
                self.page.wait_for_load_state("domcontentloaded", timeout=5_000)
                new_node = node.with_url(self.page.url)
                desc = f"click({action.logical_name!r})"

            elif action.kind == "select":
                self.page.locator(action.selector).select_option(action.value)
                new_node = node.with_field(action.logical_name, action.value)
                desc = f"select({action.logical_name!r}, {action.value!r})"

            elif action.kind == "navigate":
                self.page.goto(action.value, wait_until="domcontentloaded")
                new_node = node.with_url(self.page.url)
                desc = f"navigate({action.value!r})"

            elif action.kind == "dismiss_popup":
                self.page.keyboard.press("Escape")
                new_node = node.with_popup(None)
                desc = "dismiss_popup"

            else:
                return None, ""

            return new_node, desc

        except Exception as exc:                             # noqa: BLE001
            logger.debug("A* action %s failed: %s", action, exc)
            return None, ""

    # ------------------------------------------------------------------
    # Goal check
    # ------------------------------------------------------------------

    def _is_goal(self) -> bool:
        url = _normalise_url(self.page.url)

        # URL match
        if self.goal.url_patterns and self._h.is_goal_url(url):
            return True

        # Visible text match
        for pattern in self.goal.text_patterns:
            try:
                if self.page.locator(f"text={pattern}").is_visible():
                    return True
            except Exception:                                # noqa: BLE001
                pass

        # Element presence
        for sel in self.goal.element_selectors:
            try:
                if self.page.locator(sel).is_visible():
                    return True
            except Exception:                                # noqa: BLE001
                pass

        return False


# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────

def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)
