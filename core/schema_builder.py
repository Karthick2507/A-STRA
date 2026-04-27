"""ASTRA schema builder - converts preflight outputs into FieldSchema objects."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from schemas.field_schema import (
    AStarConfig,
    DataHints,
    Field,
    FieldSchema,
    GoalCondition,
    Section,
)
from utils.env_loader import ENV
from utils.logger import logger


def build_schemas_from_preflight(
    dom_findings: Optional[Dict[str, Any]] = None,
    network_findings: Optional[Dict[str, Any]] = None,
) -> Dict[str, FieldSchema]:
    """Build both UI and API schemas from preflight analyser outputs."""
    results: Dict[str, FieldSchema] = {}

    if dom_findings:
        results["ui"] = build_ui_schema(dom_findings)
        logger.preflight(f"Built UI schema with {sum(len(s.fields) for s in results['ui'].sections)} fields")

    if network_findings:
        results["api"] = build_api_schema(network_findings)
        logger.preflight(f"Built API schema with {sum(len(s.fields) for s in results['api'].sections)} fields")

    return results


def build_ui_schema(dom_findings: Dict[str, Any]) -> FieldSchema:
    """Convert DOM analyser findings into a UI FieldSchema."""
    dom_fields: List[Dict[str, Any]] = dom_findings.get("fields", [])

    section = Section(
        id="auto_ui",
        name="Auto-detected UI Fields",
        order=1,
        fields=[
            Field(
                name=f.get("name", f.get("id", f"field_{i}")),
                type=_normalise_input_type(f.get("type", "text")),
                label=f.get("label") or f.get("placeholder"),
                selector=_build_selector(f),
                required=f.get("required", False),
                priority=_infer_priority(f),
                data_hints=DataHints(
                    valid_examples=f.get("validExamples"),
                    enum_values=f.get("options"),
                ),
            )
            for i, f in enumerate(dom_fields)
        ],
    )

    return FieldSchema(
        id="ui-auto-generated-v1",
        name="Auto-Generated UI Schema",
        version="1.0.0",
        type="ui",
        base_url=ENV.BASE_URL,
        target_endpoint=ENV.TARGET_PAGE_URL,
        sections=[section],
        goal_conditions=[
            GoalCondition(type="url_contains", value="/success"),
        ],
        astar_config=AStarConfig(),
    )


def build_api_schema(network_findings: Dict[str, Any]) -> FieldSchema:
    """Convert network interceptor findings into an API FieldSchema."""
    endpoints: List[Dict[str, Any]] = network_findings.get("endpoints", [])
    # Use the first POST endpoint as the primary target
    primary = next(
        (e for e in endpoints if e.get("method", "").upper() == "POST"), None
    )
    if not primary:
        primary = endpoints[0] if endpoints else {}

    inferred_fields = primary.get("inferredFields", [])

    section = Section(
        id="auto_api",
        name="Auto-detected API Fields",
        order=1,
        fields=[
            Field(
                name=f.get("name", f"field_{i}"),
                type=_json_type_to_field_type(f.get("type", "string")),
                required=f.get("required", False),
                priority=_infer_priority(f),
                data_hints=DataHints(
                    valid_examples=f.get("examples"),
                ),
            )
            for i, f in enumerate(inferred_fields)
        ],
    )

    return FieldSchema(
        id="api-auto-generated-v1",
        name="Auto-Generated API Schema",
        version="1.0.0",
        type="api",
        base_url=ENV.BASE_URL,
        target_endpoint=primary.get("path", "/api/register"),
        sections=[section],
        goal_conditions=[
            GoalCondition(type="status_code", value="201"),
        ],
        astar_config=AStarConfig(),
    )


def _normalise_input_type(raw: str) -> str:
    mapping = {
        "text": "text", "email": "email", "password": "password",
        "number": "number", "tel": "tel", "url": "url",
        "select": "select", "select-one": "select",
        "radio": "radio", "checkbox": "checkbox",
        "textarea": "textarea", "date": "date",
        "file": "file", "hidden": "hidden",
    }
    return mapping.get(raw.lower(), "text")


def _json_type_to_field_type(json_type: str) -> str:
    return {"string": "text", "number": "number", "integer": "number",
            "boolean": "checkbox", "array": "text", "object": "text"}.get(json_type, "text")


def _build_selector(f: Dict[str, Any]) -> str:
    if f.get("id"):
        return f"#{f['id']}"
    if f.get("name"):
        return f"[name='{f['name']}']"
    if f.get("selector"):
        return f["selector"]
    return ""


def _infer_priority(f: Dict[str, Any]) -> int:
    name = (f.get("name") or "").lower()
    high_priority = ["email", "username", "password", "name"]
    medium_priority = ["phone", "country", "terms", "confirm"]
    if any(k in name for k in high_priority):
        return 9
    if any(k in name for k in medium_priority):
        return 7
    return f.get("priority", 5)
