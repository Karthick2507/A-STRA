"""
ASTRA-v2 Self-Healing Pipeline Orchestrator.

HealerOrchestrator.heal(page, broken_record) runs the 6-strategy pipeline,
ML re-ranks candidates, picks the best above min_confidence, verifies it on
the current page, then silently promotes it to the registry.

Call flow
─────────
  1. IdStrategy       → candidates (conf ~0.99)
  2. NameStrategy     → candidates (conf ~0.95)
  3. AriaStrategy     → candidates (conf ≤0.95)
  4. ClassStrategy    → candidates (conf ≤0.85)
  5. DomNeighbourStrategy → candidates (conf 0.65-0.70)
  6. RegistryStrategy → candidates (conf 0.55-0.75)

  ML re-rank: builds 16-dim feature vector per candidate; blends ML score
  with heuristic confidence. Weight shifts toward ML once a model is trained.

  Winner is written to the registry.  Features for winner (label=1) and hard
  negatives (label=0) are appended to the JSONL training dataset.

Usage
─────
    orchestrator = HealerOrchestrator(registry, config=CONFIG.self_healing)
    result = orchestrator.heal(page, broken_record)
    if result.success:
        page.locator(result.selector).click()
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.logging import logger
from Prism_view.self_healing.locator_registry import LocatorRecord, LocatorRegistry
from Prism_view.self_healing.strategies.base import HealCandidate
from Prism_view.self_healing.strategies import (
    IdStrategy, NameStrategy, AriaStrategy,
    ClassStrategy, DomNeighbourStrategy, RegistryStrategy,
)
from Prism_view.self_healing.ml.feature_extractor import FeatureExtractor
from Prism_view.self_healing.ml.predictor import HealerPredictor
from Prism_view.self_healing.ml.trainer import append_training_row

if TYPE_CHECKING:
    from playwright.sync_api import Page


# ──────────────────────────────────────────────────────────────────────────────
# Result container
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HealResult:
    """Outcome of one healing attempt."""
    success:       bool
    logical_name:  str
    selector:      str          = ""
    selector_kind: str          = ""
    source:        str          = ""
    confidence:    float        = 0.0
    candidates_tried: int       = 0
    elapsed_ms:    float        = 0.0
    record:        Optional[LocatorRecord] = None
    reason:        str          = ""           # failure reason when success=False

    def __repr__(self) -> str:
        if self.success:
            return (
                f"HealResult(ok, {self.logical_name!r} → {self.selector!r} "
                f"via {self.source} conf={self.confidence:.2f})"
            )
        return f"HealResult(FAIL, {self.logical_name!r}: {self.reason})"


# ──────────────────────────────────────────────────────────────────────────────
# Healing config (mirrors CONFIG.self_healing fields)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HealingConfig:
    enabled:             bool  = True
    auto_apply_silent:   bool  = True
    min_confidence:      float = 0.75
    ml_blend_weight:     float = 0.40     # fraction given to ML when model is trained
    max_candidates:      int   = 15       # cap across all strategies
    training_data_path:  str   = "Data/locators/training_data.jsonl"
    hard_negative_limit: int   = 3        # max label-0 rows per healing event


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

class HealerOrchestrator:
    """Run the full 6-strategy + ML pipeline for one broken locator."""

    def __init__(
        self,
        registry: LocatorRegistry,
        config:   Optional[HealingConfig] = None,
        predictor: Optional[HealerPredictor] = None,
    ) -> None:
        self.registry  = registry
        self.cfg       = config or HealingConfig()
        self.extractor = FeatureExtractor()
        self.predictor = predictor or HealerPredictor()
        self._build_pipeline()

    def _build_pipeline(self) -> None:
        self._strategies = [
            IdStrategy(),
            NameStrategy(),
            AriaStrategy(),
            ClassStrategy(),
            DomNeighbourStrategy(),
            RegistryStrategy(self.registry),
        ]

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def heal(
        self,
        page:   "Page",
        broken: LocatorRecord,
        dry_run: bool = False,
    ) -> HealResult:
        """Attempt to find a live replacement for `broken` on `page`.

        Args:
            page:    Playwright Page; must be on the same URL as the broken locator.
            broken:  The LocatorRecord that failed to resolve.
            dry_run: If True, propose candidates but do NOT update the registry or
                     write training data.

        Returns:
            HealResult with success=True and the new selector, or success=False.
        """
        if not self.cfg.enabled:
            return HealResult(
                success=False,
                logical_name=broken.logical_name,
                reason="self-healing disabled in config",
            )

        t0 = time.perf_counter()
        logger.heal(
            "Healing %r on %s (selector=%r was broken)",
            broken.logical_name, page.url, broken.selector,
        )

        # 1. Gather candidates from all strategies
        candidates = self._run_strategies(page, broken)
        if not candidates:
            return HealResult(
                success=False,
                logical_name=broken.logical_name,
                candidates_tried=0,
                elapsed_ms=_ms(t0),
                reason="no candidates proposed by any strategy",
            )

        # 2. ML re-rank
        ranked = self._ml_rerank(broken, candidates)

        # 3. Pick best candidate above threshold
        winner = self._pick_winner(ranked)
        if winner is None:
            return HealResult(
                success=False,
                logical_name=broken.logical_name,
                candidates_tried=len(ranked),
                elapsed_ms=_ms(t0),
                reason=(
                    f"best candidate confidence {ranked[0].confidence:.3f} "
                    f"< min_confidence {self.cfg.min_confidence}"
                    if ranked else "no candidates"
                ),
            )

        # 4. Final live verification (guard against race between propose and use)
        if not self._verify_live(page, winner.selector):
            return HealResult(
                success=False,
                logical_name=broken.logical_name,
                candidates_tried=len(ranked),
                elapsed_ms=_ms(t0),
                reason=f"winner selector {winner.selector!r} no longer present on page",
            )

        # 5. Persist to registry (unless dry run)
        new_record: Optional[LocatorRecord] = None
        if not dry_run and self.cfg.auto_apply_silent:
            new_record = self.registry.replace_with_healed(
                logical_name=broken.logical_name,
                new_selector=winner.selector,
                new_kind=winner.selector_kind,
                heal_source=winner.source,
                confidence=winner.confidence,
                page_url=page.url,
                attributes=winner.attributes,
            )

        # 6. Collect training data
        if not dry_run:
            self._record_training_data(broken, ranked, winner)

        elapsed = _ms(t0)
        logger.heal(
            "Healed %r → %r (source=%s conf=%.2f) in %.0fms",
            broken.logical_name, winner.selector, winner.source, winner.confidence, elapsed,
        )

        return HealResult(
            success=True,
            logical_name=broken.logical_name,
            selector=winner.selector,
            selector_kind=winner.selector_kind,
            source=winner.source,
            confidence=winner.confidence,
            candidates_tried=len(ranked),
            elapsed_ms=elapsed,
            record=new_record,
        )

    # ------------------------------------------------------------------
    # Strategy execution
    # ------------------------------------------------------------------

    def _run_strategies(
        self, page: "Page", broken: LocatorRecord
    ) -> List[HealCandidate]:
        seen: Dict[str, HealCandidate] = {}

        for strategy in self._strategies:
            try:
                proposals = strategy.propose(page, broken)
            except Exception as exc:                          # noqa: BLE001
                logger.debug("Strategy %s raised: %s", strategy.name, exc)
                continue

            for candidate in proposals:
                if candidate.selector not in seen:
                    seen[candidate.selector] = candidate

            # Short-circuit: if id/name matched with near-certain confidence, stop
            if seen and max(c.confidence for c in seen.values()) >= 0.98:
                logger.debug("Short-circuit: near-certain match, skipping remaining strategies")
                break

        all_candidates = sorted(seen.values())               # HealCandidate.__lt__ sorts desc
        return all_candidates[: self.cfg.max_candidates]

    # ------------------------------------------------------------------
    # ML re-ranking
    # ------------------------------------------------------------------

    def _ml_rerank(
        self,
        broken:     LocatorRecord,
        candidates: List[HealCandidate],
    ) -> List[HealCandidate]:
        """Blend heuristic confidence with ML score and re-sort."""
        is_trained = self.predictor.mode in ("onnx", "sklearn")
        blend_w = self.cfg.ml_blend_weight if is_trained else 0.0

        feature_vectors: List[List[float]] = []
        for c in candidates:
            vec = self.extractor.extract(
                broken_attrs=broken.attributes,
                broken_neighbours=broken.neighbours,
                candidate_attrs=c.attributes,
                candidate_neighbours={},     # strategies don't capture neighbours
            )
            feature_vectors.append(vec)

        ml_scores = self.predictor.predict_batch(feature_vectors)

        reranked: List[HealCandidate] = []
        for c, ml_score in zip(candidates, ml_scores):
            if blend_w > 0:
                blended = (1.0 - blend_w) * c.confidence + blend_w * ml_score
            else:
                blended = c.confidence
            reranked.append(HealCandidate(
                selector=c.selector,
                selector_kind=c.selector_kind,
                confidence=round(min(1.0, blended), 4),
                source=c.source,
                attributes=c.attributes,
                rationale=c.rationale + (
                    f" [ml_score={ml_score:.3f}]" if is_trained else ""
                ),
            ))

        reranked.sort()                                       # desc by confidence
        return reranked

    # ------------------------------------------------------------------
    # Selection & verification
    # ------------------------------------------------------------------

    def _pick_winner(
        self, ranked: List[HealCandidate]
    ) -> Optional[HealCandidate]:
        if not ranked:
            return None
        best = ranked[0]
        if best.confidence >= self.cfg.min_confidence:
            return best
        return None

    def _verify_live(self, page: "Page", selector: str) -> bool:
        try:
            return bool(page.query_selector(selector))
        except Exception:                                     # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # Training data collection
    # ------------------------------------------------------------------

    def _record_training_data(
        self,
        broken:     LocatorRecord,
        ranked:     List[HealCandidate],
        winner:     HealCandidate,
    ) -> None:
        """Append label=1 for winner, label=0 for hard-negative near-misses."""
        winner_vec = self.extractor.extract(
            broken_attrs=broken.attributes,
            broken_neighbours=broken.neighbours,
            candidate_attrs=winner.attributes,
            candidate_neighbours={},
        )
        append_training_row(
            features=winner_vec,
            label=1,
            metadata={
                "logical_name": broken.logical_name,
                "selector": winner.selector,
                "source": winner.source,
                "confidence": winner.confidence,
            },
            path=self.cfg.training_data_path,
        )

        # Hard negatives: up to N candidates that were not the winner
        neg_count = 0
        for c in ranked:
            if neg_count >= self.cfg.hard_negative_limit:
                break
            if c.selector == winner.selector:
                continue
            neg_vec = self.extractor.extract(
                broken_attrs=broken.attributes,
                broken_neighbours=broken.neighbours,
                candidate_attrs=c.attributes,
                candidate_neighbours={},
            )
            append_training_row(
                features=neg_vec,
                label=0,
                metadata={
                    "logical_name": broken.logical_name,
                    "selector": c.selector,
                    "source": c.source,
                    "confidence": c.confidence,
                },
                path=self.cfg.training_data_path,
            )
            neg_count += 1

        logger.debug(
            "Training data: 1 positive + %d negative rows for %r",
            neg_count, broken.logical_name,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)
