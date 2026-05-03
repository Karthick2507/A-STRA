# Corporate Coding Standards for PRISM Shadow Coding

## Overview

PRISM's shadow_coding now supports **automatic enforcement of corporate coding standards** in generated code. This guide shows you the different approaches to teach shadow_coding your organization's best practices.

---

## Four Approaches to Enforce Standards

### **Approach 1: Use Predefined Standards (Easiest)**

Choose from 4 built-in standard profiles:

```python
from Prism_view.shadow_coding.corporate_standards import get_standards
from Prism_view.shadow_coding.formatter import CorporateCodeFormatter

# Load a predefined standard
standards = get_standards("standard")  # or "minimal", "strict", "security"
formatter = CorporateCodeFormatter(standards)

# Format generated code
formatted_ui = formatter.format_ui_py(raw_ui_code)
formatted_data = formatter.format_data_json(raw_data_json)
formatted_base = formatter.format_base_page_py(raw_base_code)
```

**Available Profiles:**

| Profile | Use Case | Features |
|---------|----------|----------|
| `minimal` | Quick POCs | No docstrings, minimal logging |
| `standard` | Default | Type hints, docstrings, structured logging |
| `strict` | Enterprise | Try-except, retry logic, error handling |
| `security` | Compliance | Mask sensitive data, strict validation |

---

### **Approach 2: Define Custom Standards**

Create organization-specific standards without modifying code:

```python
from Prism_view.shadow_coding.corporate_standards import custom_standards

standards = custom_standards(
    company_name="Acme Corporation",
    copyright_notice="© 2026 Acme Corp. All rights reserved.",
    max_line_length=120,
    docstring_style="google",
    log_level="debug",
    include_retry_logic=True,
    mask_sensitive_logs=True,
    sensitive_fields=["password", "api_key", "token", "email", "phone"],
)

formatter = CorporateCodeFormatter(standards)
```

**Customizable Properties (15+):**

```python
CorporateStandards(
    # Imports & Structure
    include_type_hints: bool = True
    include_docstrings: bool = True
    docstring_style: str = "google"  # "google", "numpy", "sphinx"
    
    # Naming
    method_naming: str = "snake_case"
    class_naming: str = "PascalCase"
    constant_naming: str = "UPPER_SNAKE_CASE"
    
    # Logging
    log_level: str = "info"
    include_timing_logs: bool = True
    include_validation_logs: bool = True
    
    # Code Organization
    max_line_length: int = 100
    group_methods_by_category: bool = True
    
    # Error Handling
    include_try_except: bool = True
    raise_custom_exceptions: bool = True
    include_retry_logic: bool = False
    
    # Testing
    include_assertions: bool = True
    include_wait_conditions: bool = True
    assertion_style: str = "playwright"
    
    # Security
    mask_sensitive_logs: bool = True
    sensitive_fields: list = ["password", "api_key", "token"]
    
    # Data & Mocking
    data_format: str = "json"
    include_mock_data: bool = False
    faker_usage: bool = False
    
    # Headers
    file_header: str = None
    copyright_notice: str = None
    company_name: str = ""
)
```

---

### **Approach 3: Load from Config File**

Store standards in `config.json` for environment-specific enforcement:

```json
{
  "shadow_coding": {
    "corporate_standard": "strict",
    "copyright_notice": "© 2026 Your Company",
    "max_line_length": 100,
    "mask_sensitive_logs": true,
    "sensitive_fields": ["password", "api_key", "token", "email"]
  }
}
```

Usage:

```python
from core.config import CONFIG
from Prism_view.shadow_coding.corporate_standards import get_standards

standard_name = CONFIG.shadow_coding.get("corporate_standard", "standard")
standards = get_standards(standard_name)
formatter = CorporateCodeFormatter(standards)
```

---

### **Approach 4: Extend CodeEnhancer (Recommended for Integration)**

Subclass `CodeEnhancer` to apply standards automatically:

```python
from Prism_view.shadow_coding import CodeEnhancer
from Prism_view.shadow_coding.corporate_standards import get_standards
from Prism_view.shadow_coding.formatter import CorporateCodeFormatter

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
        """Enhance with corporate formatting applied."""
        result = super().enhance_file(raw_path, output_dir)
        
        # Apply formatting (implementation extends formatter.py)
        # formatted_ui = self.formatter.format_ui_py(result["ui"])
        # ... write formatted files ...
        
        return result

# Usage in main.py
enhancer = CorporateCodeEnhancer(corporate_standard="strict")
result = enhancer.enhance_file("raw_test.py")
```

---

## What Gets Customized?

### **Generated `{entity}_UI.py`**

| Standard | Example Changes |
|----------|-----------------|
| Minimal | Removes docstrings, no type hints |
| Standard | Keeps all docstrings, type hints |
| Strict | Wraps in try-except, adds retry logic |
| Security | Masks passwords in logs: `item.get("password", "***MASKED***")` |

**Before:**
```python
def create_videos(self, videos_list: List[Dict]) -> None:
    """Create Videos from list."""
    for item in videos_list:
        logger.info(f"Creating Video: {item}")
        self.page.get_by_role("textbox", name="Video Title").fill(item["Title1"])
```

**After (Security Standard):**
```python
"""
Videos page object and action orchestration.

© 2026 Your Company. All rights reserved.

Generated by PRISM Shadow Coding enhancer.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from Base_page import BasePage

logger = logging.getLogger(__name__)

class Videos(BasePage):
    """Create Videos with security-masked logging."""
    
    def create_videos(
        self,
        od_name: str,
        headers: Dict,
        videos_list: List[Dict],
        skip_create_if_exists: bool = False,
    ) -> None:
        """Create Videos from a list of item dicts.
        
        Args:
            od_name: Operation name
            headers: HTTP headers
            videos_list: List of video data
            skip_create_if_exists: Skip if exists
        """
        for item in videos_list:
            try:
                logger.info(f"Creating Video: {item.get('Title1', 'N/A')}")
                # Password/secret fields are masked in logs
                self.page.get_by_role("textbox", name="Video Title").fill(
                    item["Title1"]
                )
                # ... more code ...
            except Exception as e:
                logger.error(f"Failed to create video: {e}")
                raise CustomPRISMException(f"Video creation failed: {e}") from e
```

---

### **Generated `Base_page.py`**

Gets corporate header & method organization:

```python
"""
Base page — common / reusable Playwright helper methods.

© 2026 Your Company. All rights reserved.

Generated by PRISM Shadow Coding enhancer.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from playwright.sync_api import BrowserContext, Page, expect

logger = logging.getLogger(__name__)


class BasePage:
    """Base class providing shared UI actions and login utilities."""
    
    # ── Login Methods ──────────────────────────────────────────────────────
    
    def mrm_login(self, network: str, username: str = "", password: str = "") -> None:
        """Log in to MRM system."""
        # ... implementation ...
    
    # ── Navigation Methods ─────────────────────────────────────────────────
    
    def direct_to_network_items(self, item_type: str) -> None:
        """Navigate to Network Items section."""
        # ... implementation ...
```

---

### **Generated `{entity}_Data.json`**

Optionally adds copyright header (JSON comment):

```json
// © 2026 Your Company. All rights reserved.

{
    "MRM": [
        {
            "NetworkName": "YourNetwork",
            "Videos": [
                {
                    "Title1": "TestRUN",
                    "Description": "Test Run",
                    "StartDate": "2025-01-30"
                }
            ]
        }
    ]
}
```

---

## Implementation Timeline

### **Phase 1 (Now)** ✅
- Define `CorporateStandards` dataclass
- Create `CorporateCodeFormatter` with basic formatting
- Add predefined profiles + custom_standards() helper

### **Phase 2 (Next)**
- Extend formatter to apply all 15+ customizations
- Add validation layer (e.g., line length, naming conventions)
- Create corporate linting checks

### **Phase 3 (Future)**
- Full integration into `CodeEnhancer.enhance_file()`
- Config file support
- Multi-organization standard profiles
- IDE plugin templates

---

## Example: Setting Up for Your Organization

### **Step 1: Define Standards (do this once)**

```python
# Save in config.json or corporate_standards.py
from Prism_view.shadow_coding.corporate_standards import custom_standards

YOUR_ORG_STANDARDS = custom_standards(
    company_name="Acme Corporation",
    copyright_notice="© 2026 Acme Corp. All rights reserved.",
    max_line_length=100,
    docstring_style="google",
    include_retry_logic=True,
    mask_sensitive_logs=True,
    sensitive_fields=["password", "api_key", "token", "email", "ssn"],
)
```

### **Step 2: Use in Shadow Coding**

```python
from Prism_view.shadow_coding import CodeEnhancer
from Prism_view.shadow_coding.formatter import CorporateCodeFormatter
from corporate_standards import YOUR_ORG_STANDARDS

enhancer = CodeEnhancer()
formatter = CorporateCodeFormatter(YOUR_ORG_STANDARDS)

# Generate and format
result = enhancer.enhance(raw_playwright_code)
formatted = {
    "ui": formatter.format_ui_py(result["ui"]),
    "data": formatter.format_data_json(result["data"]),
    "base_page": formatter.format_base_page_py(result["base_page"]),
}
```

### **Step 3: Write Output**

```python
output_dir = Path("Prism_view/shadow_coding/sessions")
output_dir.mkdir(parents=True, exist_ok=True)

(output_dir / "Videos_UI.py").write_text(formatted["ui"])
(output_dir / "Videos_Data.json").write_text(formatted["data"])
(output_dir / "Base_page.py").write_text(formatted["base_page"])
```

---

## Files Added

- `Prism_view/shadow_coding/corporate_standards.py` — Standards definitions
- `Prism_view/shadow_coding/formatter.py` — Formatting engine
- `examples/shadow_coding_corporate_example.py` — Usage examples
- `docs/CORPORATE_STANDARDS_GUIDE.md` — This file

---

## Next Steps

1. **Customize for your org:** Run `custom_standards(...)` with your conventions
2. **Integrate:** Use `CorporateCodeFormatter` in your shadow_coding workflow
3. **Extend:** Add organization-specific validation in `formatter.py`
4. **Document:** Add your org's coding guidelines as a new predefined standard

---

## Questions?

Check the examples in `examples/shadow_coding_corporate_example.py` for ready-to-run code patterns.
