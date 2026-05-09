"""
Role registry — single source of truth for shadow_coding slate roles.

Decision 2: Fixed predefined roles. New roles cannot be added ad-hoc; they
must be registered here with their output file template and description.
This keeps slate config, style profile, and code_enhancer aligned.

Usage:
    from Prism_view.shadow_coding.roles import ROLES, ROLE_NAMES, validate_role

    for role in ROLE_NAMES:
        spec = ROLES[role]
        print(spec.output_template)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class RoleSpec:
    """Defines one fixed role: where its slate drives output."""
    name: str
    description: str
    output_template: str        # e.g. "{entity}_UI.py" — {entity} is filled at runtime
    output_dir: str             # relative to project root
    is_singleton: bool = False  # True for roles like ui_page (one shared file, not per-entity)


ROLES: Dict[str, RoleSpec] = {
    "ui_action": RoleSpec(
        name="ui_action",
        description="UI action methods (click, fill, navigate). Drives per-entity page object.",
        output_template="{entity}_UI.py",
        output_dir="Prism_view/UI/pages",
    ),
    "ui_locator": RoleSpec(
        name="ui_locator",
        description="Locator definitions, separated from actions for maintainability.",
        output_template="{entity}_Locators.py",
        output_dir="Prism_view/UI/pages",
    ),
    "ui_page": RoleSpec(
        name="ui_page",
        description="Shared base page class. One file for the whole framework.",
        output_template="Base_page.py",
        output_dir="Prism_view/UI/pages",
        is_singleton=True,
    ),
    "api_test": RoleSpec(
        name="api_test",
        description="API test class style.",
        output_template="{entity}_test.py",
        output_dir="API/tests",
    ),
    "data_verify": RoleSpec(
        name="data_verify",
        description="Data fixtures and assertion helpers.",
        output_template="{entity}_Data.json",
        output_dir="Data/fixtures",
    ),
    "controller": RoleSpec(
        name="controller",
        description="Test controller / orchestrator that wires page objects + fixtures.",
        output_template="{entity}_Controller.py",
        output_dir="Prism_view/UI/controllers",
    ),
    "action_class": RoleSpec(
        name="action_class",
        description="Test controller / orchestrator that wires page objects + fixtures.",
        output_template="{entity}_action_class.py",
        output_dir="Prism_view/UI/action",
    ),
}


ROLE_NAMES: Tuple[str, ...] = tuple(ROLES.keys())


def validate_role(role: str) -> None:
    """Raise ValueError if `role` is not a registered role name."""
    if role not in ROLES:
        raise ValueError(
            f"Unknown role '{role}'. Must be one of: {', '.join(ROLE_NAMES)}"
        )


def output_path_for(role: str, entity: str = "") -> str:
    """Resolve the output file path for a role + entity name.

    For singleton roles (ui_page), entity is ignored.
    """
    validate_role(role)
    spec = ROLES[role]
    filename = spec.output_template if spec.is_singleton else spec.output_template.format(entity=entity)
    return f"{spec.output_dir}/{filename}"
