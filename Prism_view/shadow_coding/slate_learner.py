"""
SlateLearner — orchestrates the full style-learning pipeline.

Flow:
    corporate_slate.{py|ts|js|java}
            ↓
    language plugin (AST / regex parser)
            ↓
    StyleProfile dataclass
            ↓  (optional)
    sklearn block classifier → ONNX
            ↓
    style_profile.json   ← code_enhancer.py reads this at runtime
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from Prism_view.shadow_coding.slate_parser import get_parser, SUPPORTED_EXTENSIONS, StyleProfile
from Prism_view.shadow_coding.roles import ROLE_NAMES, validate_role

logger = logging.getLogger(__name__)

_DEFAULT_PROFILE_PATH = Path("Prism_view/shadow_coding/style_profile.json")
_DEFAULT_CLASSIFIER_DIR = Path("Prism_view/shadow_coding/ml")


class SlateLearner:
    """Reads a corporate slate file and updates style_profile.json."""

    def __init__(
        self,
        profile_path: str | Path = _DEFAULT_PROFILE_PATH,
        classifier_dir: str | Path = _DEFAULT_CLASSIFIER_DIR,
    ) -> None:
        self.profile_path    = Path(profile_path)
        self.classifier_dir  = Path(classifier_dir)

    # ── Public API ────────────────────────────────────────────────────────

    def learn(self, slate_path: str | Path, train_classifier: bool = True) -> StyleProfile:
        """Parse slate file, update style_profile.json, optionally train block classifier.

        Args:
            slate_path: Path to corporate_slate.{py|ts|js|java}
            train_classifier: Whether to train the sklearn block classifier from slate blocks.

        Returns:
            The extracted StyleProfile.
        """
        slate_path = Path(slate_path)
        if not slate_path.exists():
            raise FileNotFoundError(f"Slate file not found: {slate_path}")

        parser = get_parser(slate_path)
        if parser is None:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise ValueError(
                f"Unsupported slate file extension '{slate_path.suffix}'. "
                f"Supported: {supported}"
            )

        logger.info("Learning style from slate: %s (language=%s)", slate_path, slate_path.suffix)
        source = slate_path.read_text(encoding="utf-8")
        profile = parser.parse(source, file_path=str(slate_path))

        self._save_profile(profile)
        logger.info("Style profile saved → %s", self.profile_path)

        if train_classifier:
            self._train_block_classifier(source, profile)

        return profile

    def learn_all(
        self,
        slates_config: dict[str, dict],
        train_classifier: bool = True,
    ) -> dict[str, StyleProfile]:
        """Learn style from multiple role-keyed slate files.

        Args:
            slates_config: Mapping of role → {file, language} from config.json slates block.
            train_classifier: Whether to train block classifier per role.

        Returns:
            Dict of role → StyleProfile for each slate that was found and parsed.
        """
        results: dict[str, StyleProfile] = {}
        role_profiles: dict[str, dict] = {}

        for role, entry in slates_config.items():
            try:
                validate_role(role)
            except ValueError as exc:
                logger.warning("Skipping unregistered role: %s", exc)
                continue
            slate_path = Path(entry.get("file", ""))
            if not slate_path.exists():
                logger.warning("Slate for role '%s' not found at %s — skipping.", role, slate_path)
                continue
            try:
                profile = self.learn(slate_path, train_classifier=train_classifier)
                results[role] = profile
                role_profiles[role] = profile.to_dict()
                logger.info("Learned role '%s' from %s", role, slate_path)
            except (ValueError, OSError) as exc:
                logger.warning("Failed to learn role '%s': %s", role, exc)

        if role_profiles:
            self._save_role_profiles(role_profiles)

        return results

    def _save_role_profiles(self, role_profiles: dict[str, dict]) -> None:
        """Merge per-role profiles into the by_role section of style_profile.json."""
        data: dict = {}
        if self.profile_path.exists():
            with open(self.profile_path, encoding="utf-8") as f:
                data = json.load(f)
        data.setdefault("by_role", {})
        for role, profile_dict in role_profiles.items():
            data["by_role"][role] = profile_dict
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.info("by_role profiles saved → %s (roles: %s)", self.profile_path, list(role_profiles))

    def load_profile(self) -> dict:
        """Load the current style_profile.json, or return defaults if missing."""
        if self.profile_path.exists():
            with open(self.profile_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    # ── Internal ──────────────────────────────────────────────────────────

    def _save_profile(self, profile: StyleProfile) -> None:
        data = profile.to_dict()
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _train_block_classifier(self, source: str, profile: StyleProfile) -> None:
        """Train sklearn GradientBoosting block classifier from slate source blocks.

        Extracts logical blocks (groups of consecutive non-blank lines), builds
        feature vectors, fits a classifier, and exports ONNX + pkl.
        Skips gracefully if sklearn / skl2onnx / numpy are not installed.
        """
        try:
            import numpy as np
            from sklearn.ensemble import GradientBoostingClassifier
            import joblib
        except ImportError:
            logger.warning("sklearn/numpy not installed — skipping block classifier training.")
            return

        blocks = self._extract_blocks(source)
        if len(blocks) < 4:
            logger.warning("Too few blocks (%d) to train classifier — need ≥ 4.", len(blocks))
            return

        X = np.array([self._block_features(b) for b in blocks], dtype=np.float32)
        y = np.array([self._label_block(b) for b in blocks], dtype=np.int32)

        clf = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        clf.fit(X, y)

        self.classifier_dir.mkdir(parents=True, exist_ok=True)
        pkl_path = self.classifier_dir / "block_classifier.pkl"
        joblib.dump(clf, pkl_path)
        logger.info("Block classifier saved → %s (%d samples)", pkl_path, len(blocks))

        # ONNX export
        try:
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType

            onnx_model = convert_sklearn(
                clf,
                initial_types=[("input", FloatTensorType([None, X.shape[1]]))],
                target_opset=17,
            )
            onnx_path = self.classifier_dir / "block_classifier.onnx"
            with open(onnx_path, "wb") as f:
                f.write(onnx_model.SerializeToString())
            logger.info("ONNX block classifier saved → %s", onnx_path)

            # Update profile json with trained=True
            data = self.load_profile()
            data.setdefault("ml", {})
            data["ml"]["classifier_trained"]  = True
            data["ml"]["training_samples"]    = len(blocks)
            data["ml"]["generated_at"]        = datetime.now(timezone.utc).isoformat()
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        except ImportError:
            logger.warning("skl2onnx not installed — ONNX export skipped (pkl still saved).")

    @staticmethod
    def _extract_blocks(source: str) -> list[list[str]]:
        """Split source into logical blocks separated by blank lines."""
        blocks, current = [], []
        for line in source.splitlines():
            if line.strip():
                current.append(line)
            elif current:
                blocks.append(current)
                current = []
        if current:
            blocks.append(current)
        return blocks

    @staticmethod
    def _block_features(lines: list[str]) -> list[float]:
        """14-dim feature vector per block for block classification."""
        text = "\n".join(lines).lower()
        return [
            float(".fill("     in text),
            float(".click()"   in text),
            float(".goto("     in text or "navigate(" in text),
            float("login"      in text or "sign in"  in text),
            float("password"   in text),
            float("network items" in text or "menu"  in text),
            float("date"       in text or "calendar" in text),
            float("create"     in text or "save"     in text or "submit" in text),
            float("assert"     in text or "expect("  in text),
            float("logger"     in text or "log."     in text or "console" in text),
            float(len(lines)),
            float("try"        in text),
            float(" for "      in text),
            float(" if "       in text),
        ]

    @staticmethod
    def _label_block(lines: list[str]) -> int:
        """Heuristic label for training — label_map in style_profile.json."""
        text = "\n".join(lines).lower()
        if "login" in text or "password" in text:
            return 0  # login
        if "network items" in text or ".goto(" in text or "navigate(" in text:
            return 1  # navigation
        if ".fill(" in text:
            return 2  # form_fill
        if "date" in text or "calendar" in text:
            return 3  # date_picker
        if "create" in text or "submit" in text or "save" in text:
            return 4  # submit
        if "assert" in text or "expect(" in text:
            return 5  # assertion
        return 6       # unknown
