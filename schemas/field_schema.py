"""ASTRA core field schema types and utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums / literals
# ---------------------------------------------------------------------------

FIELD_TYPES = [
    "text", "email", "password", "number", "tel", "url",
    "select", "radio", "checkbox", "textarea", "date",
    "file", "hidden", "submit", "button",
]

THREAT_LEVELS = ["NONE", "LOW", "MEDIUM", "HIGH"]


# ---------------------------------------------------------------------------
# Validation rule
# ---------------------------------------------------------------------------

@dataclass
class ValidationRule:
    type: str  # 'minLength' | 'maxLength' | 'pattern' | 'required' | 'min' | 'max'
    value: Any
    message: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidationRule":
        return cls(
            type=d["type"],
            value=d["value"],
            message=d.get("message"),
        )


# ---------------------------------------------------------------------------
# Data hints
# ---------------------------------------------------------------------------

@dataclass
class DataHints:
    valid_examples: Optional[List[str]] = None
    invalid_examples: Optional[List[str]] = None
    format: Optional[str] = None
    enum_values: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataHints":
        return cls(
            valid_examples=d.get("validExamples"),
            invalid_examples=d.get("invalidExamples"),
            format=d.get("format"),
            enum_values=d.get("enumValues"),
        )


# ---------------------------------------------------------------------------
# Field (leaf element inside a Section)
# ---------------------------------------------------------------------------

@dataclass
class Field:
    name: str
    type: str
    label: Optional[str] = None
    selector: Optional[str] = None
    required: bool = True
    priority: int = 5
    validation_rules: List[ValidationRule] = field(default_factory=list)
    data_hints: Optional[DataHints] = None
    depends_on: Optional[str] = None
    children: List["ChildField"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Field":
        return cls(
            name=d["name"],
            type=d["type"],
            label=d.get("label"),
            selector=d.get("selector"),
            required=d.get("required", True),
            priority=d.get("priority", 5),
            validation_rules=[
                ValidationRule.from_dict(r) for r in d.get("validationRules", [])
            ],
            data_hints=DataHints.from_dict(d["dataHints"]) if d.get("dataHints") else None,
            depends_on=d.get("dependsOn"),
            children=[
                ChildField.from_dict(c) for c in d.get("children", [])
            ],
        )


@dataclass
class ChildField:
    name: str
    type: str
    trigger_value: str
    selector: Optional[str] = None
    required: bool = True
    priority: int = 5
    validation_rules: List[ValidationRule] = field(default_factory=list)
    data_hints: Optional[DataHints] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChildField":
        return cls(
            name=d["name"],
            type=d["type"],
            trigger_value=d["triggerValue"],
            selector=d.get("selector"),
            required=d.get("required", True),
            priority=d.get("priority", 5),
            validation_rules=[
                ValidationRule.from_dict(r) for r in d.get("validationRules", [])
            ],
            data_hints=DataHints.from_dict(d["dataHints"]) if d.get("dataHints") else None,
        )


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------

@dataclass
class Section:
    id: str
    name: str
    fields: List[Field] = field(default_factory=list)
    order: int = 0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Section":
        return cls(
            id=d["id"],
            name=d["name"],
            fields=[Field.from_dict(f) for f in d.get("fields", [])],
            order=d.get("order", 0),
        )


# ---------------------------------------------------------------------------
# Goal condition
# ---------------------------------------------------------------------------

@dataclass
class GoalCondition:
    type: str  # 'url_contains' | 'element_visible' | 'element_text' | 'status_code'
    value: str
    selector: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GoalCondition":
        return cls(
            type=d["type"],
            value=d["value"],
            selector=d.get("selector"),
        )


# ---------------------------------------------------------------------------
# A* config
# ---------------------------------------------------------------------------

@dataclass
class AStarConfig:
    max_iterations: int = 1000
    heuristic_weight: float = 1.0
    allow_optional: bool = False
    timeout_ms: int = 30000

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AStarConfig":
        return cls(
            max_iterations=d.get("maxIterations", 1000),
            heuristic_weight=d.get("heuristicWeight", 1.0),
            allow_optional=d.get("allowOptional", False),
            timeout_ms=d.get("timeoutMs", 30000),
        )


# ---------------------------------------------------------------------------
# Top-level FieldSchema
# ---------------------------------------------------------------------------

@dataclass
class FieldSchema:
    id: str
    name: str
    version: str
    type: str  # 'ui' | 'api'
    base_url: str
    target_endpoint: str
    sections: List[Section] = field(default_factory=list)
    goal_conditions: List[GoalCondition] = field(default_factory=list)
    astar_config: Optional[AStarConfig] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FieldSchema":
        return cls(
            id=d["id"],
            name=d["name"],
            version=d["version"],
            type=d["type"],
            base_url=d["baseUrl"],
            target_endpoint=d["targetEndpoint"],
            sections=[Section.from_dict(s) for s in d.get("sections", [])],
            goal_conditions=[
                GoalCondition.from_dict(g) for g in d.get("goalConditions", [])
            ],
            astar_config=AStarConfig.from_dict(d["astarConfig"]) if d.get("astarConfig") else None,
            metadata=d.get("metadata"),
        )


# ---------------------------------------------------------------------------
# ResolvedField - flat field used by A* engine
# ---------------------------------------------------------------------------

@dataclass
class ResolvedField:
    id: str
    name: str
    type: str
    section_id: str
    section_name: str
    selector: Optional[str] = None
    required: bool = True
    priority: int = 5
    validation_rules: List[ValidationRule] = field(default_factory=list)
    data_hints: Optional[DataHints] = None
    depends_on: Optional[str] = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def flatten_schema(schema: FieldSchema) -> List[ResolvedField]:
    """Flatten all sections/fields into a single list of ResolvedField."""
    resolved: List[ResolvedField] = []
    for section in schema.sections:
        for f in section.fields:
            resolved.append(
                ResolvedField(
                    id=f"{section.id}.{f.name}",
                    name=f.name,
                    type=f.type,
                    section_id=section.id,
                    section_name=section.name,
                    selector=f.selector,
                    required=f.required,
                    priority=f.priority,
                    validation_rules=f.validation_rules,
                    data_hints=f.data_hints,
                    depends_on=f.depends_on,
                )
            )
            # Expand child fields (conditional fields)
            for child in f.children:
                resolved.append(
                    ResolvedField(
                        id=f"{section.id}.{child.name}",
                        name=child.name,
                        type=child.type,
                        section_id=section.id,
                        section_name=section.name,
                        selector=child.selector,
                        required=child.required,
                        priority=child.priority,
                        validation_rules=child.validation_rules,
                        data_hints=child.data_hints,
                        depends_on=f.name,
                    )
                )
    return resolved


def get_mandatory_fields(schema: FieldSchema) -> List[ResolvedField]:
    return [f for f in flatten_schema(schema) if f.required]


def get_optional_fields(schema: FieldSchema) -> List[ResolvedField]:
    return [f for f in flatten_schema(schema) if not f.required]
