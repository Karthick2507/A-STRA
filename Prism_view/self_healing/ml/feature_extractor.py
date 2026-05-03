"""
PRISM ML Feature Extractor.

Converts a (broken_locator, candidate_element) pair into a fixed-length numeric
feature vector suitable for a Scikit-learn classifier or ONNX model.

Feature design (16 dims, all 0-1 normalised):

    1.  id_match            (1 if identical id else 0)
    2.  id_similarity       (difflib ratio on ids)
    3.  name_match          (1 if identical name else 0)
    4.  name_similarity     (difflib ratio on names)
    5.  aria_similarity     (difflib ratio on aria-label)
    6.  placeholder_sim     (difflib ratio on placeholder)
    7.  label_similarity    (difflib ratio on associated label)
    8.  class_jaccard       (Jaccard on class sets)
    9.  tag_match           (1 if same tag else 0)
    10. type_match          (1 if same type attr else 0)
    11. parent_match        (1 if same parent selector else 0)
    12. nth_match           (1 if same nth-of-type position else 0)
    13. text_similarity     (difflib ratio on innerText)
    14. visible             (1 if candidate is visible)
    15. enabled             (1 if candidate is enabled)
    16. interactive_tag     (1 if input/select/textarea/button)

Why 16? Powers-of-2 keep ONNX export tidy. Keep this module SMALL and
deterministic — both training and inference must produce identical vectors.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Set

FEATURE_NAMES = [
    "id_match", "id_similarity",
    "name_match", "name_similarity",
    "aria_similarity", "placeholder_sim", "label_similarity",
    "class_jaccard",
    "tag_match", "type_match",
    "parent_match", "nth_match",
    "text_similarity",
    "visible", "enabled", "interactive_tag",
]
FEATURE_DIM = len(FEATURE_NAMES)

INTERACTIVE_TAGS = {"input", "select", "textarea", "button", "a"}


@dataclass
class ElementFeatures:
    """16-dim feature vector + the candidate's selector + identity."""
    vector:       List[float]
    candidate_id: str                   # arbitrary identifier (often a CSS path)
    candidate_selector: str
    candidate_kind:     str

    def as_list(self) -> List[float]:
        return self.vector


def _ratio(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _to_set(value: str | None) -> Set[str]:
    if not value:
        return set()
    return {tok for tok in value.split() if tok}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    return len(inter) / len(union) if union else 0.0


class FeatureExtractor:
    """Stateless extractor — call `extract(broken, candidate)` per pair."""

    def extract(
        self,
        broken_attrs:    Dict[str, Any],
        broken_neighbours: Dict[str, Any],
        candidate_attrs: Dict[str, Any],
        candidate_neighbours: Dict[str, Any],
    ) -> List[float]:
        b_id   = broken_attrs.get("id", "") or ""
        c_id   = candidate_attrs.get("id", "") or ""
        b_name = broken_attrs.get("name", "") or ""
        c_name = candidate_attrs.get("name", "") or ""
        b_aria = broken_attrs.get("aria-label", "") or ""
        c_aria = candidate_attrs.get("aria-label", "") or ""
        b_ph   = broken_attrs.get("placeholder", "") or ""
        c_ph   = candidate_attrs.get("placeholder", "") or ""
        b_lbl  = broken_attrs.get("label", "") or ""
        c_lbl  = candidate_attrs.get("label", "") or ""
        b_tag  = (broken_attrs.get("tag", "") or "").lower()
        c_tag  = (candidate_attrs.get("tag", "") or "").lower()
        b_type = (broken_attrs.get("type", "") or "").lower()
        c_type = (candidate_attrs.get("type", "") or "").lower()
        b_text = broken_attrs.get("text", "") or ""
        c_text = candidate_attrs.get("text", "") or ""

        b_parent = broken_neighbours.get("parent_selector")
        c_parent = candidate_neighbours.get("parent_selector")
        b_nth    = broken_neighbours.get("nth")
        c_nth    = candidate_neighbours.get("nth")

        return [
            1.0 if b_id and b_id == c_id else 0.0,
            _ratio(b_id, c_id),
            1.0 if b_name and b_name == c_name else 0.0,
            _ratio(b_name, c_name),
            _ratio(b_aria, c_aria),
            _ratio(b_ph,   c_ph),
            _ratio(b_lbl,  c_lbl),
            _jaccard(_to_set(broken_attrs.get("class")), _to_set(candidate_attrs.get("class"))),
            1.0 if b_tag and b_tag == c_tag else 0.0,
            1.0 if b_type and b_type == c_type else 0.0,
            1.0 if b_parent and b_parent == c_parent else 0.0,
            1.0 if b_nth is not None and b_nth == c_nth else 0.0,
            _ratio(b_text, c_text),
            1.0 if candidate_attrs.get("visible") else 0.0,
            1.0 if candidate_attrs.get("enabled", True) else 0.0,
            1.0 if c_tag in INTERACTIVE_TAGS else 0.0,
        ]
