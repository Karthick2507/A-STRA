"""Abstract base parser — all language plugins implement this interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StyleProfile:
    """Extracted style profile from a corporate slate file."""

    source_file: Optional[str] = None
    source_language: str = "python"

    # Naming conventions
    class_style: str = "PascalCase"
    method_style: str = "snake_case"
    variable_style: str = "snake_case"
    constant_style: str = "UPPER_SNAKE_CASE"

    # Class structure
    base_class: str = "BasePage"
    base_class_import: str = "from Base_page import BasePage"
    docstring_style: str = "google"
    has_type_hints: bool = True
    has_try_except: bool = False

    # Logging
    has_logging: bool = True
    logging_init: str = "logger = logging.getLogger(__name__)"
    logging_call: str = "logger.info"
    logging_format: str = "f-string"

    # Imports (lists of raw import lines)
    imports_header: List[str] = field(default_factory=lambda: ["from __future__ import annotations"])
    imports_stdlib: List[str] = field(default_factory=lambda: ["import logging"])
    imports_typing: List[str] = field(default_factory=lambda: ["from typing import Dict, List, Optional"])
    imports_local: List[str] = field(default_factory=lambda: ["from Base_page import BasePage"])

    # Playwright
    locator_api: str = "get_by_role"
    page_accessor: str = "self.page"
    uses_expect: bool = False
    uses_async: bool = False

    # Detected block wrappers
    login_wrapper: Optional[str] = "mrm_login"
    navigation_wrapper: Optional[str] = "direct_to_network_items"
    submit_wrapper: Optional[str] = "create_btn_click"

    def to_dict(self) -> Dict:
        return {
            "version": "1.0",
            "generated_at": None,
            "source": {"file": self.source_file, "language": self.source_language},
            "naming": {
                "class_style": self.class_style,
                "method_style": self.method_style,
                "variable_style": self.variable_style,
                "constant_style": self.constant_style,
            },
            "structure": {
                "base_class": self.base_class,
                "base_class_import": self.base_class_import,
                "docstring_style": self.docstring_style,
                "has_type_hints": self.has_type_hints,
                "has_try_except": self.has_try_except,
                "has_logging": self.has_logging,
                "logging_init": self.logging_init,
                "logging_call": self.logging_call,
                "logging_format": self.logging_format,
            },
            "imports": {
                "header": self.imports_header,
                "stdlib": self.imports_stdlib,
                "typing": self.imports_typing,
                "local": self.imports_local,
            },
            "playwright": {
                "locator_api": self.locator_api,
                "page_accessor": self.page_accessor,
                "uses_expect": self.uses_expect,
                "uses_async": self.uses_async,
            },
            "blocks": {
                "login":       {"detected": self.login_wrapper is not None,      "wrapper_method": self.login_wrapper or ""},
                "navigation":  {"detected": self.navigation_wrapper is not None, "wrapper_method": self.navigation_wrapper or ""},
                "form_fill":   {"detected": False},
                "date_picker": {"detected": False},
                "submit":      {"detected": self.submit_wrapper is not None,     "wrapper_method": self.submit_wrapper or ""},
            },
            "ml": {
                "classifier_trained": False,
                "classifier_path": "Prism_view/shadow_coding/ml/block_classifier.onnx",
                "sklearn_path": "Prism_view/shadow_coding/ml/block_classifier.pkl",
                "training_samples": 0,
                "label_map": {"0": "login", "1": "navigation", "2": "form_fill",
                              "3": "date_picker", "4": "submit", "5": "assertion", "6": "unknown"},
            },
        }


class BaseSlateParser(ABC):
    """Abstract interface every language plugin must implement."""

    SUPPORTED_EXTENSIONS: List[str] = []

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    @abstractmethod
    def parse(self, source: str, file_path: Optional[str] = None) -> StyleProfile:
        """Parse source text and return a StyleProfile."""

    # ── Shared helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _detect_naming(names: List[str]) -> str:
        """Guess naming convention from a list of identifiers."""
        if not names:
            return "snake_case"
        pascal = sum(1 for n in names if n and n[0].isupper() and "_" not in n)
        snake  = sum(1 for n in names if "_" in n)
        camel  = sum(1 for n in names if n and n[0].islower() and any(c.isupper() for c in n[1:]))
        if pascal >= snake and pascal >= camel:
            return "PascalCase"
        if camel > snake:
            return "camelCase"
        return "snake_case"

    @staticmethod
    def _detect_docstring_style(text: str) -> str:
        if "Args:" in text and "Returns:" in text:
            return "google"
        if "Parameters\n" in text or "----------" in text:
            return "numpy"
        if ":param " in text or ":type " in text:
            return "sphinx"
        return "google"
