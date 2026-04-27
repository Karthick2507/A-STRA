"""ASTRA UI code generator - generates pytest Playwright UI test files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas.field_schema import FieldSchema, ResolvedField
from core.search.a_star_engine import AStarResult
from utils.logger import logger

_TESTS_DIR = Path(__file__).parent.parent / "tests" / "ui"


class UiCodeGenerator:
    def __init__(self, schema: FieldSchema, astar_result: AStarResult) -> None:
        self.schema = schema
        self.astar_result = astar_result

    def generate(self) -> List[str]:
        """Generate 3 UI test files: positive, negative, full."""
        files_generated: List[str] = []

        test_files = [
            ("test_positive.py", self._generate_positive_test),
            ("test_negative.py", self._generate_negative_test),
            ("test_full.py", self._generate_full_test),
        ]

        _TESTS_DIR.mkdir(parents=True, exist_ok=True)

        for filename, generator in test_files:
            content = generator()
            path = _TESTS_DIR / filename
            path.write_text(content, encoding="utf-8")
            files_generated.append(str(path))
            logger.codegen(f"Generated {filename}")

        return files_generated

    def _generate_positive_test(self) -> str:
        steps = self._build_steps()
        return f'''"""UI test: Positive registration flow"""
import pytest
from playwright.sync_api import Page


@pytest.mark.ui
@pytest.mark.positive
def test_registration_positive(authenticated_page: Page):
    """Test successful user registration with valid data."""
    page = authenticated_page
    page.goto("{self.schema.target_endpoint}")

    # Fill form with valid data
{steps}

    # Submit
    page.click('[type=submit], button:has-text("Submit"), button:has-text("Register")')
    page.wait_for_load_state("networkidle")

    # Assert success
    page.wait_for_url("**/success**")
    assert page.is_visible(".success-message, #success")
'''

    def _generate_negative_test(self) -> str:
        return '''"""UI test: Negative registration flows"""
import pytest
from playwright.sync_api import Page


@pytest.mark.ui
@pytest.mark.negative
def test_registration_missing_required(authenticated_page: Page):
    """Test registration fails with missing required field."""
    page = authenticated_page
    page.goto("{self.schema.target_endpoint}")

    # Fill only optional fields
    page.fill('[placeholder*="First"], #firstName', "John")
    page.click('[type=submit], button:has-text("Submit")')

    # Assert error
    assert page.is_visible(".error, [data-testid=error]")
    assert not page.is_visible(".success-message")


@pytest.mark.ui
@pytest.mark.negative
def test_registration_invalid_email(authenticated_page: Page):
    """Test registration fails with invalid email."""
    page = authenticated_page
    page.goto("{self.schema.target_endpoint}")

    page.fill('[type=email], [name=email]', "not-an-email")
    page.click('[type=submit], button:has-text("Submit")')

    assert page.is_visible(".error, [data-testid=error]")
'''

    def _generate_full_test(self) -> str:
        return '''"""UI test: Full comprehensive registration"""
import pytest
from playwright.sync_api import Page


@pytest.mark.ui
@pytest.mark.e2e
def test_registration_full_flow(authenticated_page: Page):
    """Test complete registration with all fields and validations."""
    page = authenticated_page
    page.goto("{self.schema.target_endpoint}")

    # Verify all required fields are visible
    assert page.is_visible('[name=firstName]')
    assert page.is_visible('[name=lastName]')
    assert page.is_visible('[type=email]')

    # Fill all fields
    page.fill('[name=firstName]', "John")
    page.fill('[name=lastName]', "Doe")
    page.fill('[type=email]', "john.doe@example.com")
    page.fill('[type=password]', "Secure@123")

    # Handle conditional fields if present
    if page.query_selector('[name=country]'):
        page.select_option('[name=country]', "US")

    # Accept terms
    if page.query_selector('[name=terms]'):
        page.check('[name=terms]')

    # Submit
    page.click('[type=submit], button:has-text("Register")')
    page.wait_for_load_state("networkidle")

    # Assert success
    assert page.url.endswith("/success") or "success" in page.content()
'''

    def _build_steps(self) -> str:
        """Generate type-aware Playwright fill/select/check actions."""
        steps = []
        for field in self.astar_result.path:
            selector = self._build_fallback_selector(field)
            value = self._generate_test_value(field)
            if field.type == "checkbox":
                steps.append(f'    page.check("{selector}")')
            elif field.type == "select":
                steps.append(f'    page.select_option("{selector}", "{value}")')
            elif field.type == "radio":
                steps.append(f'    page.check("{selector}")')
            else:
                steps.append(f'    page.fill("{selector}", "{value}")')
        return "\n".join(steps)

    def _build_fallback_selector(self, field: ResolvedField) -> str:
        """5-strategy selector fallback."""
        if field.selector:
            return field.selector
        strategies = [
            f'[name="{field.name}"]',
            f'#{field.name}',
            f'[data-testid="{field.name}"]',
            f'[placeholder*="{field.name}"]',
            f'label:has-text("{field.name}") + input',
        ]
        return " ,".join(strategies)

    def _generate_test_value(self, field: ResolvedField) -> str:
        """Generate type-aware test data."""
        mapping = {
            "email": "test@example.com",
            "password": "Secure@123",
            "tel": "+1234567890",
            "number": "42",
            "date": "2000-01-01",
        }
        return mapping.get(field.type, f"test_{field.name}")
