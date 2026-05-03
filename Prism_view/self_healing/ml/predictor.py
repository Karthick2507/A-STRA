"""
PRISM ML Predictor.

Runs at *inference* time inside the self-healing pipeline. Loads either:

    1. ONNX model via `onnxruntime` (preferred — small footprint, CPU-only)
    2. Sklearn `.pkl` via `joblib`            (fallback if ONNX missing)
    3. Heuristic fallback (always available)  — uses the strongest single feature

The predictor returns a confidence score 0..1 for each candidate so the healer
can re-rank the list produced by heuristic strategies.

Cold-start friendly: if no model file exists, the predictor returns the
heuristic baseline so the framework still works on first run.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from core.logging import logger
from Prism_view.self_healing.ml.feature_extractor import FEATURE_DIM

try:
    import onnxruntime as ort                                # type: ignore
    _ONNX_OK = True
except ImportError:                                          # pragma: no cover
    _ONNX_OK = False

try:
    import joblib                                            # type: ignore
    import numpy as np                                       # type: ignore
    _SKLEARN_OK = True
except ImportError:                                          # pragma: no cover
    _SKLEARN_OK = False


class HealerPredictor:
    """Score a candidate's healing-likelihood from its feature vector."""

    def __init__(
        self,
        onnx_path: str | Path = "Prism_view/self_healing/ml/models/healer_model.onnx",
        pkl_path:  str | Path = "Prism_view/self_healing/ml/models/healer_model.pkl",
    ) -> None:
        self.onnx_path = Path(onnx_path)
        self.pkl_path  = Path(pkl_path)
        self._onnx_session: Optional["ort.InferenceSession"] = None
        self._sklearn_model = None
        self._mode: str = "heuristic"

        self._load()

    def _load(self) -> None:
        if _ONNX_OK and self.onnx_path.exists():
            try:
                self._onnx_session = ort.InferenceSession(
                    str(self.onnx_path),
                    providers=["CPUExecutionProvider"],
                )
                self._mode = "onnx"
                logger.info("HealerPredictor loaded ONNX model from %s", self.onnx_path)
                return
            except Exception as exc:                         # noqa: BLE001
                logger.warning("ONNX load failed (%s) — trying sklearn fallback", exc)

        if _SKLEARN_OK and self.pkl_path.exists():
            try:
                self._sklearn_model = joblib.load(self.pkl_path)
                self._mode = "sklearn"
                logger.info("HealerPredictor loaded sklearn model from %s", self.pkl_path)
                return
            except Exception as exc:                         # noqa: BLE001
                logger.warning("sklearn load failed (%s) — using heuristic baseline", exc)

        logger.info("HealerPredictor running in heuristic mode (no model trained yet)")
        self._mode = "heuristic"

    @property
    def mode(self) -> str:
        return self._mode

    def predict(self, feature_vector: List[float]) -> float:
        """Return a 0..1 confidence score for one candidate."""
        if len(feature_vector) != FEATURE_DIM:
            return 0.0

        if self._mode == "onnx" and self._onnx_session is not None:
            try:
                arr = np.array([feature_vector], dtype=np.float32)
                outputs = self._onnx_session.run(None, {"input": arr})
                # Sklearn-converted ONNX returns: [predictions, probabilities]
                probs = outputs[1]
                if hasattr(probs, "shape") and probs.shape[-1] >= 2:
                    return float(probs[0][1])                # P(class=1)
                return float(probs[0]) if hasattr(probs, "__getitem__") else 0.5
            except Exception as exc:                         # noqa: BLE001
                logger.debug("ONNX predict failed (%s) — heuristic fallback", exc)

        if self._mode == "sklearn" and self._sklearn_model is not None:
            try:
                arr = np.array([feature_vector], dtype=np.float32)
                proba = self._sklearn_model.predict_proba(arr)
                return float(proba[0][1])
            except Exception as exc:                         # noqa: BLE001
                logger.debug("sklearn predict failed (%s) — heuristic fallback", exc)

        # Heuristic baseline: weighted average of strongest signal features
        weights = [
            0.30,  # id_match
            0.05,  # id_similarity
            0.15,  # name_match
            0.05,  # name_similarity
            0.10,  # aria_similarity
            0.05,  # placeholder_sim
            0.05,  # label_similarity
            0.10,  # class_jaccard
            0.03,  # tag_match
            0.02,  # type_match
            0.04,  # parent_match
            0.02,  # nth_match
            0.01,  # text_similarity
            0.02,  # visible
            0.005, # enabled
            0.005, # interactive_tag
        ]
        score = sum(f * w for f, w in zip(feature_vector, weights))
        return min(1.0, max(0.0, score))

    def predict_batch(self, vectors: List[List[float]]) -> List[float]:
        return [self.predict(v) for v in vectors]
