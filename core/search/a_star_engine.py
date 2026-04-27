"""ASTRA A* search engine - finds optimal field-fill order using A* algorithm."""
from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from schemas.field_schema import AStarConfig, FieldSchema, ResolvedField, flatten_schema
from core.scorer.heuristic_scorer import HeuristicScorer, ScorerState
from utils.logger import logger


@dataclass
class AStarNode:
    f_score: float
    g_score: float
    h_score: float
    field: ResolvedField
    filled: frozenset  # IDs of filled fields at this node
    path: List[str]  # field IDs in fill order

    def __lt__(self, other: "AStarNode") -> bool:
        return self.f_score < other.f_score


@dataclass
class AStarResult:
    success: bool
    path: List[ResolvedField]
    field_order: List[str]
    iterations: int
    duration_ms: float
    total_fields: int
    filled_count: int
    skipped_fields: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class AStarSearchOptions:
    include_optional: bool = False
    max_iterations: Optional[int] = None
    timeout_ms: Optional[float] = None


class AStarEngine:
    def __init__(self, schema: FieldSchema) -> None:
        self.schema = schema
        self.config: AStarConfig = schema.astar_config or AStarConfig()
        self.all_fields = flatten_schema(schema)
        self.scorer = HeuristicScorer(self.all_fields, self.config.heuristic_weight)

    # ------------------------------------------------------------------
    # Public search methods
    # ------------------------------------------------------------------

    def search(self, options: Optional[AStarSearchOptions] = None) -> AStarResult:
        """Standard A* search over required fields."""
        opts = options or AStarSearchOptions()
        candidates = [
            f for f in self.all_fields
            if f.required or opts.include_optional
        ]
        return self._run_astar(candidates, opts)

    def search_negative(self) -> AStarResult:
        """A* search targeting required fields for negative test generation."""
        candidates = [f for f in self.all_fields if f.required]
        return self._run_astar(candidates, AStarSearchOptions())

    def search_with_optional(self) -> AStarResult:
        """A* search including optional fields."""
        return self._run_astar(self.all_fields, AStarSearchOptions(include_optional=True))

    def get_search_summary(self, result: AStarResult) -> str:
        status = "SUCCESS" if result.success else "FAILED"
        return (
            f"A* Search [{status}] "
            f"fields={result.filled_count}/{result.total_fields} "
            f"iterations={result.iterations} "
            f"duration={result.duration_ms:.1f}ms"
        )

    # ------------------------------------------------------------------
    # Core A* algorithm
    # ------------------------------------------------------------------

    def _run_astar(self, candidates: List[ResolvedField], opts: AStarSearchOptions) -> AStarResult:
        max_iter = opts.max_iterations or self.config.max_iterations
        timeout_ms = opts.timeout_ms or self.config.timeout_ms
        start_time = time.time()

        # Build a lookup map
        field_map: Dict[str, ResolvedField] = {f.id: f for f in candidates}
        required_ids = frozenset(f.id for f in candidates if f.required)

        if not required_ids:
            return AStarResult(
                success=True, path=[], field_order=[],
                iterations=0, duration_ms=0.0,
                total_fields=0, filled_count=0,
            )

        state = ScorerState(total_required=len(required_ids))

        # Initialise heap with all candidate fields as starting nodes
        heap: List[AStarNode] = []
        for f in candidates:
            if not f.depends_on:  # start with independent fields only
                score = self.scorer.score_field(f, state)
                node = AStarNode(
                    f_score=score.f_score,
                    g_score=score.g_score,
                    h_score=score.h_score,
                    field=f,
                    filled=frozenset(),
                    path=[],
                )
                heapq.heappush(heap, node)

        best_path: List[str] = []
        iterations = 0

        while heap and iterations < max_iter:
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > timeout_ms:
                logger.warning(f"A* search timed out after {elapsed_ms:.0f}ms")
                break

            node = heapq.heappop(heap)
            iterations += 1

            if node.field.id in node.filled:
                continue  # already processed this field in this path

            new_filled = node.filled | {node.field.id}
            new_path = node.path + [node.field.id]

            state.filled_fields = set(new_filled)
            state.iterations = iterations

            logger.astar_step(iterations, node.field.name, node.f_score)

            # Check if goal is reached
            if required_ids.issubset(new_filled):
                best_path = new_path
                logger.goal_reached(iterations, len(new_path))
                break

            # Expand: add unfilled fields whose dependencies are satisfied
            for f in candidates:
                if f.id in new_filled:
                    continue
                if f.depends_on and f.depends_on not in state.filled_fields:
                    continue  # dependency not yet filled
                new_state = ScorerState(
                    filled_fields=set(new_filled),
                    failed_fields=state.failed_fields,
                    total_required=state.total_required,
                    iterations=iterations,
                )
                score = self.scorer.score_field(f, new_state)
                child = AStarNode(
                    f_score=score.f_score,
                    g_score=node.g_score + score.g_score,
                    h_score=score.h_score,
                    field=f,
                    filled=new_filled,
                    path=new_path,
                )
                heapq.heappush(heap, child)

        duration_ms = (time.time() - start_time) * 1000
        success = required_ids.issubset(set(best_path))

        ordered_fields = [
            field_map[fid] for fid in best_path if fid in field_map
        ]
        skipped = [
            f.name for f in candidates
            if f.id not in set(best_path) and f.required
        ]

        return AStarResult(
            success=success,
            path=ordered_fields,
            field_order=best_path,
            iterations=iterations,
            duration_ms=duration_ms,
            total_fields=len(candidates),
            filled_count=len(best_path),
            skipped_fields=skipped,
        )
