"""
PRISM OpenAPI Spec Loader.

Loads an OpenAPI 3.x (or Swagger 2.0) spec from a local file or URL and
exposes the parsed endpoints for contract testing and auto-generated API
test stubs.

Features
────────
  - Accepts JSON or YAML spec files
  - Resolves $ref references (local only)
  - Returns a list of EndpointSpec objects (method, path, summary, parameters,
    request body schema, response schemas)
  - Can generate a minimal pytest test stub for each endpoint

Usage
─────
    loader = OpenAPISpecLoader("Data/API/openapi.json")
    endpoints = loader.load()
    for ep in endpoints:
        print(ep.method, ep.path, ep.summary)

    # Generate test stubs
    loader.emit_stubs("API/tests/generated/")
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logging import logger

try:
    import yaml                                               # type: ignore
    _YAML_OK = True
except ImportError:                                          # pragma: no cover
    _YAML_OK = False


# ──────────────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class EndpointSpec:
    method:          str
    path:            str
    operation_id:    str
    summary:         str
    tags:            List[str]          = field(default_factory=list)
    parameters:      List[Dict]         = field(default_factory=list)
    request_body:    Optional[Dict]     = None
    response_schemas: Dict[str, Dict]   = field(default_factory=dict)  # status_code → schema
    security:        List[Dict]         = field(default_factory=list)

    def __repr__(self) -> str:
        return f"EndpointSpec({self.method.upper()} {self.path!r})"


# ──────────────────────────────────────────────────────────────────────────────
# Loader
# ──────────────────────────────────────────────────────────────────────────────

class OpenAPISpecLoader:
    """Parse an OpenAPI spec and expose its endpoints."""

    def __init__(self, spec_path: str | Path) -> None:
        self.spec_path = Path(spec_path)
        self._raw: Dict[str, Any] = {}
        self._endpoints: List[EndpointSpec] = []

    def load(self) -> List[EndpointSpec]:
        """Parse the spec file and return all endpoint specs."""
        self._raw = self._read_file()
        self._endpoints = self._parse_paths()
        logger.info(
            "OpenAPI spec loaded from %s — %d endpoints",
            self.spec_path, len(self._endpoints),
        )
        return self._endpoints

    @property
    def endpoints(self) -> List[EndpointSpec]:
        if not self._endpoints:
            self.load()
        return self._endpoints

    def get_by_tag(self, tag: str) -> List[EndpointSpec]:
        return [e for e in self.endpoints if tag in e.tags]

    def get_by_method(self, method: str) -> List[EndpointSpec]:
        return [e for e in self.endpoints if e.method.lower() == method.lower()]

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read_file(self) -> Dict[str, Any]:
        if not self.spec_path.exists():
            raise FileNotFoundError(f"OpenAPI spec not found at {self.spec_path}")
        text = self.spec_path.read_text(encoding="utf-8")
        suffix = self.spec_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            if not _YAML_OK:
                raise ImportError("PyYAML not installed. Run: pip install pyyaml")
            return yaml.safe_load(text)
        return json.loads(text)

    # ------------------------------------------------------------------
    # Path parsing
    # ------------------------------------------------------------------

    def _parse_paths(self) -> List[EndpointSpec]:
        endpoints: List[EndpointSpec] = []
        paths = self._raw.get("paths", {})
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() not in ("get", "post", "put", "patch", "delete", "head", "options"):
                    continue
                if not isinstance(operation, dict):
                    continue
                operation = self._resolve_refs(operation)
                endpoints.append(EndpointSpec(
                    method=method.lower(),
                    path=path,
                    operation_id=operation.get("operationId", f"{method}_{_path_to_id(path)}"),
                    summary=operation.get("summary", ""),
                    tags=operation.get("tags", []),
                    parameters=operation.get("parameters", []),
                    request_body=operation.get("requestBody"),
                    response_schemas=self._extract_responses(operation),
                    security=operation.get("security", []),
                ))
        return endpoints

    def _extract_responses(self, operation: Dict) -> Dict[str, Dict]:
        result: Dict[str, Dict] = {}
        for status_code, resp_obj in operation.get("responses", {}).items():
            content = resp_obj.get("content", {})
            for media_type, media_obj in content.items():
                result[str(status_code)] = media_obj.get("schema", {})
                break           # first media type wins
        return result

    def _resolve_refs(self, obj: Any) -> Any:
        """Shallow $ref resolver (local components/schemas only)."""
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                if ref.startswith("#/"):
                    parts = ref[2:].split("/")
                    val: Any = self._raw
                    try:
                        for part in parts:
                            val = val[part]
                        return val
                    except (KeyError, TypeError):
                        return obj
            return {k: self._resolve_refs(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._resolve_refs(i) for i in obj]
        return obj

    # ------------------------------------------------------------------
    # Stub generation
    # ------------------------------------------------------------------

    def emit_stubs(
        self,
        output_dir: str | Path = "API/tests/generated",
        client_import: str = "from API.client import APIClient",
    ) -> List[Path]:
        """Write one pytest test file per tag (or 'misc' if untagged)."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        files: List[Path] = []

        by_tag: Dict[str, List[EndpointSpec]] = {}
        for ep in self.endpoints:
            tag = ep.tags[0] if ep.tags else "misc"
            by_tag.setdefault(tag, []).append(ep)

        for tag, eps in by_tag.items():
            lines = [
                "import pytest",
                client_import,
                "",
                "",
            ]
            for ep in eps:
                fn_name = f"test_{ep.method}_{_path_to_id(ep.path)}"
                lines += [
                    f"def {fn_name}(api_client):",
                    f'    """Auto-generated stub for {ep.method.upper()} {ep.path}',
                    f'    {ep.summary}',
                    '    """',
                    f'    resp = api_client.{ep.method}("{ep.path}")',
                ]
                # Assert success status if known
                success_codes = [c for c in ep.response_schemas if c.startswith("2")]
                if success_codes:
                    codes = " or ".join(f"resp.status_code == {c}" for c in success_codes)
                    lines.append(f"    assert {codes}")
                else:
                    lines.append("    assert resp.status_code < 400")
                lines += ["", ""]

            tag_file = output_dir / f"test_{re.sub(r'[^a-z0-9]', '_', tag.lower())}.py"
            tag_file.write_text("\n".join(lines), encoding="utf-8")
            files.append(tag_file)
            logger.info("Generated API stub → %s (%d endpoints)", tag_file, len(eps))

        return files


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _path_to_id(path: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", path.lower()).strip("_")
