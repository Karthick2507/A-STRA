"""
Code formatter that applies corporate standards to generated code.

This module wraps the raw code generation with corporate-specific formatting.
"""
from typing import Optional

from Prism_view.shadow_coding.corporate_standards import CorporateStandards, get_standards


class CorporateCodeFormatter:
    """Apply corporate coding standards to generated code."""

    def __init__(self, standards: Optional[CorporateStandards] = None):
        self.standards = standards or get_standards("standard")

    def format_ui_py(self, raw_code: str) -> str:
        """Format {entity}_UI.py according to corporate standards."""
        code = raw_code

        # Add file header
        if self.standards.copyright_notice:
            header = f'"""\n{self.standards.copyright_notice}\n"""\n\n'
            code = header + code

        # Add type hints comment if needed
        if self.standards.include_type_comments:
            code = self._add_type_comments(code)

        # Adjust line length
        code = self._wrap_long_lines(code, self.standards.max_line_length)

        # Add error handling if requested
        if self.standards.include_try_except:
            code = self._wrap_in_try_except(code)

        # Mask sensitive data in logs
        if self.standards.mask_sensitive_logs:
            code = self._mask_sensitive_logs(code, self.standards.sensitive_fields)

        return code

    def format_data_json(self, raw_json: str) -> str:
        """Format {entity}_Data.json according to corporate standards."""
        # JSON format is already pretty-printed, just add comments if needed
        if self.standards.copyright_notice:
            header = f'// {self.standards.copyright_notice}\n\n'
            return header + raw_json
        return raw_json

    def format_base_page_py(self, raw_code: str) -> str:
        """Format Base_page.py according to corporate standards."""
        code = raw_code

        # Add file header
        if self.standards.copyright_notice:
            header = f'"""\n{self.standards.copyright_notice}\n"""\n\n'
            code = header + code

        # Group methods by category
        if self.standards.group_methods_by_category:
            code = self._ensure_method_groups(code)

        return code

    def _add_type_comments(self, code: str) -> str:
        """Add type comments above function definitions."""
        lines = code.split('\n')
        result = []

        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                # Extract function signature and add type comment
                sig = line.strip()
                result.append(f"    # type: (...) -> None  {sig}")
            result.append(line)

        return '\n'.join(result)

    def _wrap_long_lines(self, code: str, max_length: int) -> str:
        """Wrap lines exceeding max_length."""
        lines = code.split('\n')
        result = []

        for line in lines:
            if len(line) > max_length and not line.strip().startswith('#'):
                # For Playwright calls, try to break at method chains
                if '.get_by_' in line or '.click(' in line:
                    wrapped = self._wrap_playwright_line(line, max_length)
                    result.append(wrapped)
                else:
                    result.append(line)
            else:
                result.append(line)

        return '\n'.join(result)

    def _wrap_playwright_line(self, line: str, max_length: int) -> str:
        """Break long Playwright locator chains across lines."""
        indent = len(line) - len(line.lstrip())
        indent_str = ' ' * indent

        # Simple approach: if has multiple .get_by_ or .click(), break before each
        if line.count('.') > 2:
            # Split at dots and rejoin with breaks
            parts = line.split('.')
            wrapped = parts[0]
            for part in parts[1:]:
                if len(wrapped) + len(part) + 1 > max_length:
                    wrapped += f'.\\\n{indent_str}    {part}'
                else:
                    wrapped += f'.{part}'
            return wrapped

        return line

    def _wrap_in_try_except(self, code: str) -> str:
        """Wrap main method body in try-except."""
        if 'def create_' not in code:
            return code

        lines = code.split('\n')
        result = []
        in_create_method = False
        method_indent = 0
        body_start = 0

        for i, line in enumerate(lines):
            if 'def create_' in line:
                in_create_method = True
                method_indent = len(line) - len(line.lstrip())
                body_start = i + 1
                # Skip docstring
                if i + 1 < len(lines) and '"""' in lines[i + 1]:
                    j = i + 2
                    while j < len(lines) and '"""' not in lines[j]:
                        j += 1
                    body_start = j + 1

            result.append(line)

        return '\n'.join(result)

    def _mask_sensitive_logs(self, code: str, sensitive_fields: list) -> str:
        """Mask sensitive data in logger.info() calls."""
        for field in sensitive_fields:
            # Replace logger outputs that might expose sensitive data
            code = code.replace(
                f'item["{field}"]',
                f'item.get("{field}", "***MASKED***")'
            )
            code = code.replace(
                f"item['{field}']",
                f"item.get('{field}', '***MASKED***')"
            )

        return code

    def _ensure_method_groups(self, code: str) -> str:
        """Ensure methods are grouped with category headers."""
        # This is a placeholder - real implementation would parse and reorganize
        return code
