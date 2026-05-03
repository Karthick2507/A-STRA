"""
Corporate coding standards configuration for PRISM Shadow Coding.

Define your organization's preferred style, conventions, and best practices here.
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class CorporateStandards:
    """Corporate coding conventions for generated code."""

    # ── Imports & Structure ────────────────────────────────────────────────
    include_type_hints: bool = True
    include_docstrings: bool = True
    docstring_style: str = "google"  # "google", "numpy", "sphinx"

    # ── Naming Conventions ─────────────────────────────────────────────────
    method_naming: str = "snake_case"  # "snake_case", "camelCase"
    class_naming: str = "PascalCase"
    constant_naming: str = "UPPER_SNAKE_CASE"

    # ── Logging & Debugging ────────────────────────────────────────────────
    log_level: str = "info"  # "debug", "info", "warning"
    include_timing_logs: bool = True
    include_validation_logs: bool = True

    # ── Code Organization ─────────────────────────────────────────────────
    max_line_length: int = 100
    group_methods_by_category: bool = True  # ── Login ──, ── Navigation ──, etc.
    include_type_comments: bool = False

    # ── Error Handling ────────────────────────────────────────────────────
    include_try_except: bool = True
    raise_custom_exceptions: bool = True
    include_retry_logic: bool = False

    # ── Testing & Assertions ───────────────────────────────────────────────
    include_assertions: bool = True
    include_wait_conditions: bool = True
    assertion_style: str = "playwright"  # "playwright", "pytest", "assert"

    # ── Performance & Optimization ──────────────────────────────────────────
    use_parallel_execution: bool = False
    include_caching: bool = False
    include_lazy_loading: bool = True

    # ── Security ────────────────────────────────────────────────────────────
    mask_sensitive_logs: bool = True
    sensitive_fields: list = None  # ["password", "api_key", "token"]

    # ── Data & Mocking ───────────────────────────────────────────────────────
    data_format: str = "json"  # "json", "csv", "yaml"
    include_mock_data: bool = False
    faker_usage: bool = False

    # ── Custom Headers & Footers ────────────────────────────────────────────
    file_header: Optional[str] = None
    copyright_notice: Optional[str] = None
    company_name: str = ""

    def __post_init__(self):
        if self.sensitive_fields is None:
            self.sensitive_fields = ["password", "api_key", "token", "secret"]


# ── Predefined Standards ────────────────────────────────────────────────────

MINIMAL_STANDARDS = CorporateStandards(
    include_docstrings=False,
    include_timing_logs=False,
    include_validation_logs=False,
)

STANDARD_CORPORATE = CorporateStandards(
    include_type_hints=True,
    include_docstrings=True,
    docstring_style="google",
    log_level="info",
    include_validation_logs=True,
    group_methods_by_category=True,
)

STRICT_ENTERPRISE = CorporateStandards(
    include_type_hints=True,
    include_docstrings=True,
    docstring_style="google",
    include_try_except=True,
    raise_custom_exceptions=True,
    include_retry_logic=True,
    mask_sensitive_logs=True,
    include_assertions=True,
    max_line_length=88,
    company_name="Your Company",
)

HIGH_SECURITY = CorporateStandards(
    mask_sensitive_logs=True,
    sensitive_fields=["password", "api_key", "token", "secret", "email", "phone", "ssn"],
    include_try_except=True,
    raise_custom_exceptions=True,
    include_assertions=True,
)


# Retrieve standards by name
STANDARDS_REGISTRY: Dict[str, CorporateStandards] = {
    "minimal": MINIMAL_STANDARDS,
    "standard": STANDARD_CORPORATE,
    "strict": STRICT_ENTERPRISE,
    "security": HIGH_SECURITY,
}


def get_standards(name: str = "standard") -> CorporateStandards:
    """Get corporate standards by name.

    Args:
        name: "minimal", "standard", "strict", "security"

    Returns:
        CorporateStandards instance
    """
    return STANDARDS_REGISTRY.get(name, STANDARD_CORPORATE)


def custom_standards(**kwargs) -> CorporateStandards:
    """Create custom standards.

    Example::
        standards = custom_standards(
            company_name="Acme Corp",
            include_retry_logic=True,
            max_line_length=120
        )
    """
    defaults = STANDARD_CORPORATE.__dict__.copy()
    defaults.update(kwargs)
    return CorporateStandards(**defaults)
