"""PRISM folder scanner — discovery + classification engine."""
from .scan_result import ScannedFile, RoleAssignment, ScanResult
from .file_classifier import classify_file
from .folder_scanner import FolderScanner

__all__ = [
    "FolderScanner",
    "classify_file",
    "ScannedFile",
    "RoleAssignment",
    "ScanResult",
]
