"""Dataclasses for folder-scan results."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class ScannedFile:
    path: Path
    language: str        # python | typescript | javascript | java | data
    role: str            # one of the 6 fixed roles
    confidence: float    # 0.0 – 1.0
    signals: List[str]   # human-readable reasons that drove the classification


@dataclass
class RoleAssignment:
    role: str
    files: List[ScannedFile] = field(default_factory=list)

    @property
    def confidence_level(self) -> str:
        if not self.files:
            return "NONE"
        avg = sum(f.confidence for f in self.files) / len(self.files)
        if avg >= 0.85:
            return "HIGH"
        if avg >= 0.70:
            return "MEDIUM"
        return "LOW"

    @property
    def avg_confidence(self) -> float:
        if not self.files:
            return 0.0
        return sum(f.confidence for f in self.files) / len(self.files)


@dataclass
class ScanResult:
    root: Path
    assignments: Dict[str, RoleAssignment] = field(default_factory=dict)
    unclassified: List[ScannedFile] = field(default_factory=list)
    languages_found: List[str] = field(default_factory=list)
    total_files_scanned: int = 0

    def files_for_role(self, role: str) -> List[ScannedFile]:
        return self.assignments.get(role, RoleAssignment(role=role)).files

    def low_confidence_assignments(self) -> List[RoleAssignment]:
        return [a for a in self.assignments.values() if a.confidence_level == "LOW"]
