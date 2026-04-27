"""ASTRA heuristic scorer - computes A* g/h/f scores for form fields."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from schemas.field_schema import ResolvedField
from utils.logger import logger


@dataclass
class FieldScore:
    field_id: str
    field_name: str
    g_score: float  # cost so far
    h_score: float  # heuristic (estimated cost to goal)
    f_score: float  # g + h
    priority: int
    is_required: bool


@dataclass
class ScorerState:
    filled_fields: Set[str] = field(default_factory=set)
    failed_fields: Set[str] = field(default_factory=set)
    total_required: int = 0
    iterations: int = 0


class HeuristicScorer:
    def __init__(self, all_fields: List[ResolvedField], heuristic_weight: float = 1.0) -> None:
        self.all_fields = all_fields
        self.heuristic_weight = heuristic_weight
        self.required_fields = {f.id for f in all_fields if f.required}
        self.total_required = len(self.required_fields)

    def compute_g_score(self, field: ResolvedField, state: ScorerState) -> float:
        """Cost so far: penalise high-priority fields filled late."""
        base_cost = 1.0
        # Penalty if a dependency was already skipped
        if field.depends_on and field.depends_on not in state.filled_fields:
            base_cost += 2.0
        # Penalty for retrying a previously failed field
        if field.id in state.failed_fields:
            base_cost += 3.0
        return base_cost

    def compute_h_score(self, field: ResolvedField, state: ScorerState) -> float:
        """Heuristic: estimated remaining fields to fill."""
        remaining_required = self.required_fields - state.filled_fields
        remaining_required.discard(field.id)
        h = len(remaining_required)
        # Boost: prefer high-priority fields by reducing their h-score
        priority_bonus = (10 - field.priority) * 0.1
        return max(0.0, h - priority_bonus)

    def compute_f_score(self, g: float, h: float) -> float:
        return g + self.heuristic_weight * h

    def score_field(self, field: ResolvedField, state: ScorerState) -> FieldScore:
        g = self.compute_g_score(field, state)
        h = self.compute_h_score(field, state)
        f = self.compute_f_score(g, h)
        return FieldScore(
            field_id=field.id,
            field_name=field.name,
            g_score=g,
            h_score=h,
            f_score=f,
            priority=field.priority,
            is_required=field.required,
        )

    def rank_candidates(
        self, candidates: List[ResolvedField], state: ScorerState
    ) -> List[FieldScore]:
        scores = [self.score_field(f, state) for f in candidates]
        return sorted(scores, key=lambda s: (s.f_score, -s.priority))

    def is_goal_reached(self, state: ScorerState) -> bool:
        return self.required_fields.issubset(state.filled_fields)
