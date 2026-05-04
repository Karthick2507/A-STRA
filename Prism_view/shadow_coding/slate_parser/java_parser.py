"""Java slate parser — regex-based."""
from __future__ import annotations

import re
from typing import List, Optional

from Prism_view.shadow_coding.slate_parser.base_parser import BaseSlateParser, StyleProfile


class JavaSlateParser(BaseSlateParser):
    SUPPORTED_EXTENSIONS = [".java"]

    def parse(self, source: str, file_path: Optional[str] = None) -> StyleProfile:
        profile = StyleProfile(source_file=file_path, source_language="java")

        # ── Imports ────────────────────────────────────────────────────────
        import_lines = re.findall(r'^import\s+[\w.]+;', source, re.MULTILINE)
        stdlib_i, local_i = [], []
        for line in import_lines:
            if "playwright" in line.lower() or "basepage" in line.lower():
                local_i.append(line)
            else:
                stdlib_i.append(line)

        if stdlib_i: profile.imports_stdlib = stdlib_i
        if local_i:  profile.imports_local  = local_i
        profile.imports_header = []   # Java has no __future__
        profile.imports_typing = []   # Java generics inline

        # ── Class & base class ────────────────────────────────────────────
        cls_match = re.search(r'(?:public\s+)?class\s+(\w+)\s+extends\s+(\w+)', source)
        if cls_match:
            cls_name  = cls_match.group(1)
            base_name = cls_match.group(2)
            profile.class_style        = self._detect_naming([cls_name])
            profile.base_class         = base_name
            profile.base_class_import  = f"import com.example.pages.{base_name};"

        # ── Methods ───────────────────────────────────────────────────────
        method_names = re.findall(
            r'(?:public|private|protected)\s+\w[\w<>[\]]*\s+(\w+)\s*\(', source
        )
        if method_names:
            profile.method_style = self._detect_naming(method_names)

        # ── Type hints — always true in Java ─────────────────────────────
        profile.has_type_hints = True

        # ── Async — Java Playwright can be sync or async ──────────────────
        profile.uses_async = "CompletableFuture" in source or "async" in source.lower()

        # ── Logging ───────────────────────────────────────────────────────
        if re.search(r'(logger\.|log\.)(info|debug|warn|error)', source):
            profile.has_logging  = True
            m = re.search(r'(logger\.\w+|log\.\w+)', source)
            if m:
                profile.logging_call = m.group(1)

            # Detect format style: SLF4J uses "{}", log4j uses %s
            if '"{}"' in source or '{}' in source:
                profile.logging_format = "slf4j-placeholder"
            elif '"%s"' in source:
                profile.logging_format = "percent"
            else:
                profile.logging_format = "concat"

            # Logger init
            m2 = re.search(
                r'((?:private\s+)?(?:static\s+)?(?:final\s+)?(?:Logger|Log)\s+\w+\s*=\s*.+;)',
                source
            )
            if m2:
                profile.logging_init = m2.group(1).strip()
        elif "System.out.println" in source:
            profile.has_logging    = True
            profile.logging_call   = "System.out.println"
            profile.logging_format = "concat"
            profile.logging_init   = ""
        else:
            profile.has_logging = False

        # ── Playwright ────────────────────────────────────────────────────
        if "getByRole" in source:
            profile.locator_api = "getByRole"
        elif "getByLabel" in source:
            profile.locator_api = "getByLabel"
        elif ".locator(" in source:
            profile.locator_api = "locator"

        profile.uses_expect = "assertThat(" in source or "expect(" in source

        if "this.page" in source:
            profile.page_accessor = "this.page"
        elif "page." in source:
            profile.page_accessor = "page"

        # ── try-catch ─────────────────────────────────────────────────────
        profile.has_try_except = "try {" in source or "try{" in source

        # ── Block wrappers ─────────────────────────────────────────────────
        if "mrmLogin" not in source and "mrm_login" not in source:
            profile.login_wrapper = None
        if "directToNetworkItems" not in source and "direct_to_network_items" not in source:
            profile.navigation_wrapper = None
        if "createBtnClick" not in source and "create_btn_click" not in source:
            profile.submit_wrapper = None

        # ── Docstring style (Javadoc) ─────────────────────────────────────
        if "@param" in source or "@return" in source:
            profile.docstring_style = "javadoc"

        return profile
