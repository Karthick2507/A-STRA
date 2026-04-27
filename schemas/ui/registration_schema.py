"""ASTRA manual UI registration schema."""
from __future__ import annotations

from schemas.field_schema import (
    AStarConfig,
    DataHints,
    Field,
    FieldSchema,
    GoalCondition,
    Section,
    ValidationRule,
)
from utils.env_loader import ENV


def get_registration_ui_schema() -> FieldSchema:
    return FieldSchema(
        id="ui-registration-v1",
        name="User Registration UI",
        version="1.0.0",
        type="ui",
        base_url=ENV.BASE_URL,
        target_endpoint=ENV.TARGET_PAGE_URL,
        sections=[
            Section(
                id="personalInfo",
                name="Personal Information",
                order=1,
                fields=[
                    Field(
                        name="firstName",
                        type="text",
                        label="First Name",
                        selector="#firstName, [name=firstName], [placeholder*='First']",
                        required=True,
                        priority=9,
                        validation_rules=[
                            ValidationRule(type="minLength", value=2),
                            ValidationRule(type="maxLength", value=50),
                        ],
                        data_hints=DataHints(
                            valid_examples=["John", "Jane"],
                            invalid_examples=["J", "123"],
                        ),
                    ),
                    Field(
                        name="lastName",
                        type="text",
                        label="Last Name",
                        selector="#lastName, [name=lastName], [placeholder*='Last']",
                        required=True,
                        priority=9,
                        validation_rules=[
                            ValidationRule(type="minLength", value=2),
                            ValidationRule(type="maxLength", value=50),
                        ],
                        data_hints=DataHints(
                            valid_examples=["Doe", "Smith"],
                            invalid_examples=["D", "456"],
                        ),
                    ),
                    Field(
                        name="email",
                        type="email",
                        label="Email",
                        selector="#email, [name=email], [type=email]",
                        required=True,
                        priority=10,
                        validation_rules=[
                            ValidationRule(type="pattern", value="^[^@]+@[^@]+\\.[^@]+$"),
                        ],
                        data_hints=DataHints(
                            valid_examples=["user@example.com"],
                            invalid_examples=["notanemail"],
                            format="email",
                        ),
                    ),
                    Field(
                        name="phone",
                        type="tel",
                        label="Phone",
                        selector="#phone, [name=phone], [type=tel]",
                        required=False,
                        priority=5,
                        data_hints=DataHints(
                            valid_examples=["+1234567890"],
                        ),
                    ),
                ],
            ),
            Section(
                id="credentials",
                name="Account Credentials",
                order=2,
                fields=[
                    Field(
                        name="username",
                        type="text",
                        label="Username",
                        selector="#username, [name=username], [placeholder*='Username']",
                        required=True,
                        priority=10,
                        validation_rules=[
                            ValidationRule(type="minLength", value=3),
                            ValidationRule(type="maxLength", value=30),
                        ],
                        data_hints=DataHints(
                            valid_examples=["john_doe", "alice123"],
                        ),
                    ),
                    Field(
                        name="password",
                        type="password",
                        label="Password",
                        selector="#password, [name=password], [type=password]",
                        required=True,
                        priority=10,
                        validation_rules=[
                            ValidationRule(type="minLength", value=8),
                        ],
                        data_hints=DataHints(
                            valid_examples=["Secure@123"],
                            invalid_examples=["short"],
                        ),
                    ),
                    Field(
                        name="confirmPassword",
                        type="password",
                        label="Confirm Password",
                        selector="#confirmPassword, [name=confirmPassword], [placeholder*='Confirm']",
                        required=True,
                        priority=9,
                        data_hints=DataHints(
                            valid_examples=["Secure@123"],
                        ),
                    ),
                ],
            ),
            Section(
                id="preferences",
                name="Preferences",
                order=3,
                fields=[
                    Field(
                        name="country",
                        type="select",
                        label="Country",
                        selector="#country, [name=country], select[id*='country']",
                        required=True,
                        priority=8,
                        data_hints=DataHints(
                            enum_values=["US", "GB", "CA", "AU", "IN"],
                        ),
                    ),
                    Field(
                        name="termsAccepted",
                        type="checkbox",
                        label="Accept Terms",
                        selector="#terms, [name=terms], [name=termsAccepted]",
                        required=True,
                        priority=6,
                        data_hints=DataHints(
                            valid_examples=["true"],
                            invalid_examples=["false"],
                        ),
                    ),
                ],
            ),
        ],
        goal_conditions=[
            GoalCondition(type="url_contains", value="/success"),
            GoalCondition(type="element_visible", value=".success-message, #success, [data-testid=success]"),
        ],
        astar_config=AStarConfig(
            max_iterations=500,
            heuristic_weight=1.0,
            allow_optional=False,
            timeout_ms=30000,
        ),
    )


REGISTRATION_UI_SCHEMA = get_registration_ui_schema()
