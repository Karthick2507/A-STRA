"""Walk a directory tree and classify every supported file."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Optional, Set

from .file_classifier import classify_file, _EXT_LANG
from .scan_result import RoleAssignment, ScanResult, ScannedFile

log = logging.getLogger(__name__)

_DEFAULT_IGNORE: Set[str] = {
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".pytest_cache",
    "vendor", "target", "build", "dist",
    ".venv", "venv", "env",
    ".idea", ".vscode",
}

_SUPPORTED_EXTS: Set[str] = set(_EXT_LANG.keys())


class FolderScanner:
    """Recursively scan *root* and classify files by PRISM role.

    Args:
        root: Directory to scan.
        ignore_dirs: Additional directory names to skip (merged with defaults).
        max_depth: Maximum recursion depth (None = unlimited).
    """

    def __init__(
        self,
        root: str | Path,
        ignore_dirs: Optional[Iterable[str]] = None,
        max_depth: Optional[int] = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._ignore = _DEFAULT_IGNORE | set(ignore_dirs or [])
        self._max_depth = max_depth

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def scan(self) -> ScanResult:
        """Walk the folder tree and return a fully populated ScanResult."""
        result = ScanResult(root=self._root)

        classified: List[ScannedFile] = []
        for path in self._walk(self._root, depth=0):
            scanned = classify_file(path)
            if scanned is None:
                continue
            classified.append(scanned)

        result.total_files_scanned = len(classified)

        # Group by role
        assignments: dict[str, RoleAssignment] = {}
        unclassified: List[ScannedFile] = []
        langs: Set[str] = set()

        for sf in classified:
            langs.add(sf.language)
            if sf.confidence < 0.30:
                unclassified.append(sf)
            else:
                if sf.role not in assignments:
                    assignments[sf.role] = RoleAssignment(role=sf.role)
                assignments[sf.role].files.append(sf)

        result.assignments = assignments
        result.unclassified = unclassified
        result.languages_found = sorted(langs - {"data"})
        return result

    # ──────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────

    def _walk(self, directory: Path, depth: int) -> Iterable[Path]:
        if self._max_depth is not None and depth > self._max_depth:
            return

        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            log.warning("Permission denied: %s", directory)
            return

        for entry in entries:
            if entry.is_dir():
                if entry.name in self._ignore or entry.name.startswith("."):
                    continue
                yield from self._walk(entry, depth + 1)
            elif entry.is_file() and entry.suffix.lower() in _SUPPORTED_EXTS:
                yield entry
