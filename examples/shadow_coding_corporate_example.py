"""
Example: Using PRISM shadow_coding with corporate coding standards.

This shows how to apply your organization's coding standards to generated code.
"""
from pathlib import Path

from Prism_view.shadow_coding import ShadowRecorder, CodeEnhancer
from Prism_view.shadow_coding.corporate_standards import (
    get_standards,
    custom_standards,
)
from Prism_view.shadow_coding.formatter import CorporateCodeFormatter


# ── Option 1: Use Predefined Standards ────────────────────────────────────

def example_standard_corporate():
    """Generate code using standard corporate standards."""
    standards = get_standards("standard")
    formatter = CorporateCodeFormatter(standards)

    # Record raw code
    recorder = ShadowRecorder()
    session = recorder.start(url="https://mrm.example.com/login")
    # ... user interactions ...
    result = recorder.stop()

    # Enhance with formatting
    enhancer = CodeEnhancer()
    raw_code_dict = enhancer.enhance(result.code)

    # Apply corporate standards
    formatted_ui = formatter.format_ui_py(raw_code_dict["ui"])
    formatted_data = formatter.format_data_json(raw_code_dict["data"])
    formatted_base = formatter.format_base_page_py(raw_code_dict["base_page"])

    # Write formatted files
    output_dir = Path("Prism_view/shadow_coding/sessions")
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "Videos_UI.py").write_text(formatted_ui)
    (output_dir / "Videos_Data.json").write_text(formatted_data)
    (output_dir / "Base_page.py").write_text(formatted_base)

    print(f"✅ Generated corporate-standard code in {output_dir}")


# ── Option 2: Use Strict Enterprise Standards ───────────────────────────

def example_strict_enterprise():
    """Generate code using strict enterprise standards (try-except, retry logic, etc)."""
    standards = get_standards("strict")
    formatter = CorporateCodeFormatter(standards)

    # ... same flow as above, but with strict standards applied ...
    pass


# ── Option 3: Custom Organization Standards ────────────────────────────

def example_custom_standards():
    """Define custom standards for your organization."""
    standards = custom_standards(
        company_name="Acme Corporation",
        copyright_notice="Copyright © 2026 Acme Corporation. All rights reserved.",
        max_line_length=120,
        docstring_style="google",
        log_level="debug",
        include_retry_logic=True,
        mask_sensitive_logs=True,
        sensitive_fields=["password", "api_key", "token", "secret", "username"],
    )

    formatter = CorporateCodeFormatter(standards)

    # ... use formatter as above ...
    pass


# ── Option 4: Define Corporate Standards in Config ──────────────────────

def example_config_driven():
    """Load standards from config file."""
    # In your config.json:
    # {
    #   "shadow_coding": {
    #     "corporate_standard": "strict",
    #     "copyright_notice": "© 2026 Your Company",
    #     "max_line_length": 100
    #   }
    # }

    from core.config import CONFIG

    standard_name = CONFIG.shadow_coding.get("corporate_standard", "standard")
    standards = get_standards(standard_name)

    formatter = CorporateCodeFormatter(standards)
    # ... use formatter ...
    pass


# ── Recommended: Extend CodeEnhancer ────────────────────────────────────

class CorporateCodeEnhancer(CodeEnhancer):
    """CodeEnhancer that applies corporate standards automatically."""

    def __init__(
        self,
        output_dir=None,
        corporate_standard: str = "standard",
    ):
        super().__init__(output_dir)
        self.standards = get_standards(corporate_standard)
        self.formatter = CorporateCodeFormatter(self.standards)

    def enhance_file(self, raw_path, output_dir=None):
        """Enhance file with corporate standards applied."""
        # Get raw enhancement
        result = super().enhance_file(raw_path, output_dir)

        # Apply corporate formatting (in real implementation)
        # formatted_ui = self.formatter.format_ui_py(result["ui_content"])
        # ... etc ...

        return result


# ── Usage in main.py ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("""
    Corporate Coding Standards Integration
    ──────────────────────────────────────

    Usage Options:

    1. Use predefined standards:
       >>> standards = get_standards("standard")
       >>> formatter = CorporateCodeFormatter(standards)

    2. Define custom standards:
       >>> standards = custom_standards(
       ...     company_name="Your Company",
       ...     max_line_length=120,
       ...     include_retry_logic=True
       ... )
       >>> formatter = CorporateCodeFormatter(standards)

    3. Use extended enhancer:
       >>> enhancer = CorporateCodeEnhancer(
       ...     corporate_standard="strict"
       ... )
       >>> enhancer.enhance_file("raw_code.py")

    4. Load from config:
       >>> # Set in config.json:
       >>> # "shadow_coding": { "corporate_standard": "strict" }
       >>> standards = get_standards(CONFIG.shadow_coding["corporate_standard"])
    """)
