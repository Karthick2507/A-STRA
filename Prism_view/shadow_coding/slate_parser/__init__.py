"""Language parser plugins — auto-selected by file extension."""
from pathlib import Path
from typing import Optional

from Prism_view.shadow_coding.slate_parser.base_parser import BaseSlateParser, StyleProfile
from Prism_view.shadow_coding.slate_parser.python_parser import PythonSlateParser
from Prism_view.shadow_coding.slate_parser.typescript_parser import TypeScriptSlateParser
from Prism_view.shadow_coding.slate_parser.java_parser import JavaSlateParser

_REGISTRY: list[BaseSlateParser] = [
    PythonSlateParser(),
    TypeScriptSlateParser(),
    JavaSlateParser(),
]

SUPPORTED_EXTENSIONS = {
    ext for parser in _REGISTRY for ext in parser.SUPPORTED_EXTENSIONS
}


def get_parser(path: Path) -> Optional[BaseSlateParser]:
    """Return the right parser for a file, or None if unsupported."""
    for parser in _REGISTRY:
        if parser.can_parse(path):
            return parser
    return None


__all__ = [
    "BaseSlateParser", "StyleProfile",
    "PythonSlateParser", "TypeScriptSlateParser", "JavaSlateParser",
    "get_parser", "SUPPORTED_EXTENSIONS",
]
