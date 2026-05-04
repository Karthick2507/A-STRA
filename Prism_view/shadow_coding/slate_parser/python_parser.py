"""Python slate parser — uses stdlib ast for accurate extraction."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Optional

from Prism_view.shadow_coding.slate_parser.base_parser import BaseSlateParser, StyleProfile


class PythonSlateParser(BaseSlateParser):
    SUPPORTED_EXTENSIONS = [".py"]

    def parse(self, source: str, file_path: Optional[str] = None) -> StyleProfile:
        profile = StyleProfile(source_file=file_path, source_language="python")

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return profile  # return defaults on unparseable input

        # ── Imports ───────────────────────────────────────────────────────
        header, stdlib, typing_imports, local = [], [], [], []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                line = self._reconstruct_import_from(node)
                if node.module == "__future__":
                    header.append(line)
                elif node.module in ("typing",):
                    typing_imports.append(line)
                elif node.module and "." not in node.module and node.module[0].islower():
                    stdlib.append(line)
                else:
                    local.append(line)
            elif isinstance(node, ast.Import):
                line = "import " + ", ".join(a.name for a in node.names)
                stdlib.append(line)

        if header:   profile.imports_header  = header
        if stdlib:   profile.imports_stdlib  = stdlib
        if typing_imports: profile.imports_typing = typing_imports
        if local:    profile.imports_local   = local

        # ── Classes ────────────────────────────────────────────────────────
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if classes:
            cls = classes[0]
            profile.class_style = self._detect_naming([cls.name])

            # Base class
            if cls.bases:
                base = cls.bases[0]
                if isinstance(base, ast.Name):
                    profile.base_class = base.id
                    # Find the matching import line
                    for imp in local:
                        if base.id in imp:
                            profile.base_class_import = imp
                            break

            # Methods
            methods = [n for n in ast.walk(cls) if isinstance(n, ast.FunctionDef)]
            method_names = [m.name for m in methods if not m.name.startswith("_")]
            profile.method_style = self._detect_naming(method_names)

            # Type hints: check if any method has annotated args
            profile.has_type_hints = any(
                any(a.annotation for a in m.args.args if a.arg != "self")
                for m in methods
            )

            # try-except presence
            profile.has_try_except = any(
                isinstance(n, ast.Try) for n in ast.walk(cls)
            )

            # Docstring style
            all_docstrings = []
            for m in methods:
                if (m.body and isinstance(m.body[0], ast.Expr)
                        and isinstance(m.body[0].value, ast.Constant)
                        and isinstance(m.body[0].value.value, str)):
                    all_docstrings.append(m.body[0].value.value)
            if all_docstrings:
                profile.docstring_style = self._detect_docstring_style("\n".join(all_docstrings))

        # ── Logging ────────────────────────────────────────────────────────
        log_calls = re.findall(r'(logger\.\w+|logging\.\w+|log\.\w+)\s*\(', source)
        if log_calls:
            profile.has_logging = True
            profile.logging_call = log_calls[0].split("(")[0]
            profile.logging_format = "f-string" if 'f"' in source or "f'" in source else "percent"
        else:
            profile.has_logging = False

        # Logger init line
        m = re.search(r'(logger\s*=\s*.+getLogger.+)', source)
        if m:
            profile.logging_init = m.group(1).strip()

        # ── Playwright ────────────────────────────────────────────────────
        if "get_by_role" in source:
            profile.locator_api = "get_by_role"
        elif "get_by_label" in source:
            profile.locator_api = "get_by_label"
        elif "locator(" in source:
            profile.locator_api = "locator"

        profile.uses_expect = "expect(" in source
        profile.uses_async = "async def" in source

        if "self.page" in source:
            profile.page_accessor = "self.page"
        elif "self._page" in source:
            profile.page_accessor = "self._page"

        # ── Block wrappers ────────────────────────────────────────────────
        if "mrm_login" not in source:
            profile.login_wrapper = None
        if "direct_to_network_items" not in source:
            profile.navigation_wrapper = None
        if "create_btn_click" not in source:
            profile.submit_wrapper = None

        return profile

    @staticmethod
    def _reconstruct_import_from(node: ast.ImportFrom) -> str:
        names = ", ".join(
            (a.asname and f"{a.name} as {a.asname}") or a.name
            for a in node.names
        )
        dots = "." * (node.level or 0)
        module = node.module or ""
        return f"from {dots}{module} import {names}"
