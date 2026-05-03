"""
PRISM ML Trainer.

Trains a Scikit-learn classifier on collected (broken, candidate, is_match)
triples. The model learns to score 0..1 how likely a candidate is to be the
correct healed locator.

Training data is collected automatically by the framework:
    - Whenever a heuristic strategy succeeds (and the test passes), the
      (broken_attrs, candidate_attrs, label=1) row is appended to
      Data/locators/training_data.jsonl.
    - For every successful match we also synthesise hard negatives by sampling
      sibling elements that *did not* match (label=0).

Cold-start: the first ~50 healing events bootstrap the model. After that the
trainer can be re-run periodically (e.g. nightly Jenkins job).

Both `.pkl` (sklearn) and `.onnx` (cross-platform inference) are produced.
ONNX is preferred at runtime — predictor falls back to pkl if onnx missing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from core.logging import logger

try:
    import numpy as np
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    import joblib
    _SKLEARN_OK = True
except ImportError:                                          # pragma: no cover
    _SKLEARN_OK = False

try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    _ONNX_OK = True
except ImportError:                                          # pragma: no cover
    _ONNX_OK = False

from Prism_view.self_healing.ml.feature_extractor import FEATURE_DIM


@dataclass
class TrainingResult:
    accuracy:   float
    roc_auc:    float
    n_train:    int
    n_test:     int
    pkl_path:   Path
    onnx_path:  Path | None


class HealerTrainer:
    """Train a healer ranking model from collected JSONL training data."""

    def __init__(
        self,
        training_data_path: str | Path = "Data/locators/training_data.jsonl",
        sklearn_model_path: str | Path = "Prism_view/self_healing/ml/models/healer_model.pkl",
        onnx_model_path:    str | Path = "Prism_view/self_healing/ml/models/healer_model.onnx",
    ) -> None:
        self.training_data_path = Path(training_data_path)
        self.sklearn_model_path = Path(sklearn_model_path)
        self.onnx_model_path    = Path(onnx_model_path)

    def _load_dataset(self) -> Tuple["np.ndarray", "np.ndarray"]:
        if not self.training_data_path.exists():
            raise FileNotFoundError(
                f"Training data not found at {self.training_data_path}. "
                f"Run some healing first — the framework writes events here automatically."
            )

        X: list[list[float]] = []
        y: list[int]         = []
        with open(self.training_data_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    vec = row["features"]
                    label = int(row["label"])
                    if len(vec) != FEATURE_DIM:
                        continue
                    X.append(vec)
                    y.append(label)
                except (json.JSONDecodeError, KeyError):
                    continue
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)

    def train(self, min_samples: int = 30) -> TrainingResult:
        if not _SKLEARN_OK:
            raise RuntimeError("scikit-learn not installed. `pip install scikit-learn joblib skl2onnx`.")

        X, y = self._load_dataset()
        if len(X) < min_samples:
            raise RuntimeError(
                f"Need at least {min_samples} training rows; have {len(X)}. "
                f"Keep using the framework — it auto-collects rows during healing events."
            )

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y if len(set(y)) > 1 else None,
        )
        model = GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42,
        )
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        try:
            y_score = model.predict_proba(X_test)[:, 1]
            roc_auc = roc_auc_score(y_test, y_score)
        except Exception:                                    # noqa: BLE001
            roc_auc = float("nan")

        # ── Persist sklearn pkl
        self.sklearn_model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self.sklearn_model_path)
        logger.info("Saved sklearn model → %s", self.sklearn_model_path)

        # ── Persist ONNX (preferred runtime format)
        onnx_path: Path | None = None
        if _ONNX_OK:
            try:
                initial_type = [("input", FloatTensorType([None, FEATURE_DIM]))]
                onnx_model = convert_sklearn(model, initial_types=initial_type)
                self.onnx_model_path.parent.mkdir(parents=True, exist_ok=True)
                self.onnx_model_path.write_bytes(onnx_model.SerializeToString())
                onnx_path = self.onnx_model_path
                logger.info("Saved ONNX model → %s", self.onnx_model_path)
            except Exception as exc:                         # noqa: BLE001
                logger.warning("ONNX export failed (will fall back to pkl): %s", exc)

        result = TrainingResult(
            accuracy=accuracy,
            roc_auc=roc_auc,
            n_train=len(X_train),
            n_test=len(X_test),
            pkl_path=self.sklearn_model_path,
            onnx_path=onnx_path,
        )
        logger.info(
            "Healer model trained: acc=%.3f auc=%.3f  train=%d test=%d",
            accuracy, roc_auc, result.n_train, result.n_test,
        )
        return result


def append_training_row(
    features: List[float],
    label: int,
    metadata: dict | None = None,
    path: str | Path = "Data/locators/training_data.jsonl",
) -> None:
    """Append a labelled (features, label) row. Called from the healer."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"features": features, "label": int(label), "meta": metadata or {}}
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
