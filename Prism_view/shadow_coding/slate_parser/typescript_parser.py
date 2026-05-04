"""TypeScript / JavaScript slate parser — regex-based (no Node.js required)."""
from __future__ import annotations

import re
from typing import List, Optional

from Prism_view.shadow_coding.slate_parser.base_parser import BaseSlateParser, StyleProfile


class TypeScriptSlateParser(BaseSlateParser):
    SUPPORTED_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx"]

    def parse(self, source: str, file_path: Optional[str] = None) -> StyleProfile:
        profile = StyleProfile(source_file=file_path, source_language="typescript")

        # ── Imports ────────────────────────────────────────────────────────
        import_lines = re.findall(r'^import\s+.+;?\s*$', source, re.MULTILINE)
        header, stdlib_i, typing_i, local_i = [], [], [], []
        for line in import_lines:
            line = line.strip()
            if "from '@playwright" in line or 'from "@playwright' in line:
                local_i.append(line)
            elif "from './" in line or 'from "./' in line:
                local_i.append(line)
            else:
                stdlib_i.append(line)

        if stdlib_i:  profile.imports_stdlib = stdlib_i
        if local_i:   profile.imports_local  = local_i

        # ── Class & base class ────────────────────────────────────────────
        cls_match = re.search(r'class\s+(\w+)\s+extends\s+(\w+)', source)
        if cls_match:
            cls_name, base_name = cls_match.group(1), cls_match.group(2)
            profile.class_style  = self._detect_naming([cls_name])
            profile.base_class   = base_name
            profile.base_class_import = f"import {{ {base_name} }} from './Base_page';"

        # ── Methods ───────────────────────────────────────────────────────
        method_names = re.findall(
            r'(?:async\s+)?(?:public\s+)?(?:private\s+)?(\w+)\s*\(', source
        )
        method_names = [n for n in method_names
                        if n not in ("if", "for", "while", "switch", "catch", "constructor")]
        if method_names:
            profile.method_style = self._detect_naming(method_names)

        # ── Type hints ────────────────────────────────────────────────────
        # TS has types if we see `: string`, `: number`, `Promise<`, etc.
        profile.has_type_hints = bool(
            re.search(r':\s*(string|number|boolean|void|Promise|Dict|List|Map)', source)
        )

        # ── Async ─────────────────────────────────────────────────────────
        profile.uses_async = "async " in source or "await " in source

        # ── Logging ───────────────────────────────────────────────────────
        if "console.log" in source:
            profile.has_logging    = True
            profile.logging_call   = "console.log"
            profile.logging_format = "template-literal" if "`" in source else "concat"
            profile.logging_init   = ""
        elif re.search(r'(this\.logger|this\.log|logger\.)', source):
            profile.has_logging  = True
            m = re.search(r'(this\.logger\.\w+|this\.log\.\w+|logger\.\w+)', source)
            if m:
                profile.logging_call = m.group(1)
            profile.logging_format = "template-literal" if "`" in source else "concat"
            m2 = re.search(r'((?:private|protected|readonly)?\s*\w*logger\w*\s*=\s*.+)', source)
            if m2:
                profile.logging_init = m2.group(1).strip()
        else:
            profile.has_logging = False

        # ── Playwright ────────────────────────────────────────────────────
        # TS Playwright uses camelCase: getByRole, getByLabel, locator
        if "getByRole" in source:
            profile.locator_api = "getByRole"
        elif "getByLabel" in source:
            profile.locator_api = "getByLabel"
        elif ".locator(" in source:
            profile.locator_api = "locator"

        profile.uses_expect = "expect(" in source

        if "this.page" in source:
            profile.page_accessor = "this.page"
        elif "page." in source:
            profile.page_accessor = "page"

        # ── try-except ────────────────────────────────────────────────────
        profile.has_try_except = "try {" in source or "try{" in source

        # ── Block wrappers ─────────────────────────────────────────────────
        if "mrmLogin" not in source and "mrm_login" not in source:
            profile.login_wrapper = None
        if "directToNetworkItems" not in source and "direct_to_network_items" not in source:
            profile.navigation_wrapper = None
        if "createBtnClick" not in source and "create_btn_click" not in source:
            profile.submit_wrapper = None

        # ── Docstring style (JSDoc) ────────────────────────────────────────
        if "@param" in source:
            profile.docstring_style = "jsdoc"

        return profile
