"""PRISM folder scanner — discovery + classification engine."""
from .scan_result import ScannedFile, RoleAssignment, ScanResult
from .file_classifier import classify_file
from .folder_scanner import FolderScanner
from .scan_report import format_report, format_role_detail
from .interactive_cli import review_scan

__all__ = [
    "FolderScanner",
    "classify_file",
    "review_scan",
    "format_report",
    "format_role_detail",
    "ScannedFile",
    "RoleAssignment",
    "ScanResult",
]
