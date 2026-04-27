"""ASTRA manual API registration schema."""
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


def get_registration_api_schema() -> FieldSchema:
    return FieldSchema(
        id="api-registration-v1",
        name="User Registration API",
        version="1.0.0",
        type="api",
        base_url=ENV.BASE_URL,
        target_endpoint="/api/register",
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
                        required=True,
                        priority=9,
                        validation_rules=[
                            ValidationRule(type="minLength", value=2, message="Min 2 chars"),
                            ValidationRule(type="maxLength", value=50, message="Max 50 chars"),
                            ValidationRule(type="pattern", value="^[a-zA-Z]+$", message="Letters only"),
                        ],
                        data_hints=DataHints(
                            valid_examples=["John", "Jane", "Alice"],
                            invalid_examples=["J", "123", "John123"],
                            format="alpha",
                        ),
                    ),
                    Field(
                        name="lastName",
                        type="text",
                        label="Last Name",
                        required=True,
                        priority=9,
                        validation_rules=[
                            ValidationRule(type="minLength", value=2, message="Min 2 chars"),
                            ValidationRule(type="maxLength", value=50, message="Max 50 chars"),
                            ValidationRule(type="pattern", value="^[a-zA-Z]+$", message="Letters only"),
                        ],
                        data_hints=DataHints(
                            valid_examples=["Doe", "Smith", "Johnson"],
                            invalid_examples=["D", "456"],
                            format="alpha",
                        ),
                    ),
                    Field(
                        name="email",
                        type="email",
                        label="Email Address",
                        required=True,
                        priority=10,
                        validation_rules=[
                            ValidationRule(type="pattern", value="^[^@]+@[^@]+\\.[^@]+$", message="Invalid email"),
                            ValidationRule(type="maxLength", value=100, message="Max 100 chars"),
                        ],
                        data_hints=DataHints(
                            valid_examples=["user@example.com", "test@domain.org"],
                            invalid_examples=["notanemail", "missing@tld", "@nodomain.com"],
                            format="email",
                        ),
                    ),
                    Field(
                        name="phone",
                        type="tel",
                        label="Phone Number",
                        required=False,
                        priority=5,
                        validation_rules=[
                            ValidationRule(type="pattern", value="^\\+?[1-9]\\d{9,14}$", message="Invalid phone"),
                        ],
                        data_hints=DataHints(
                            valid_examples=["+1234567890", "+44987654321"],
                            invalid_examples=["123", "abcdefghij"],
                            format="e164",
                        ),
                    ),
                ],
            ),
            Section(
                id="address",
                name="Address",
                order=2,
                fields=[
                    Field(
                        name="street",
                        type="text",
                        label="Street Address",
                        required=True,
                        priority=7,
                        validation_rules=[
                            ValidationRule(type="minLength", value=5, message="Min 5 chars"),
                            ValidationRule(type="maxLength", value=200, message="Max 200 chars"),
                        ],
                        data_hints=DataHints(
                            valid_examples=["123 Main St", "456 Oak Avenue"],
                            invalid_examples=["123"],
                        ),
                    ),
                    Field(
                        name="city",
                        type="text",
                        label="City",
                        required=True,
                        priority=7,
                        data_hints=DataHints(
                            valid_examples=["New York", "London", "Tokyo"],
                        ),
                    ),
                    Field(
                        name="country",
                        type="select",
                        label="Country",
                        required=True,
                        priority=8,
                        data_hints=DataHints(
                            enum_values=["US", "GB", "CA", "AU", "IN"],
                            valid_examples=["US", "GB"],
                            invalid_examples=["XX", "ZZ"],
                        ),
                    ),
                    Field(
                        name="zipCode",
                        type="text",
                        label="Zip / Postal Code",
                        required=False,
                        priority=4,
                        data_hints=DataHints(
                            valid_examples=["10001", "SW1A 1AA"],
                        ),
                    ),
                ],
            ),
            Section(
                id="credentials",
                name="Account Credentials",
                order=3,
                fields=[
                    Field(
                        name="username",
                        type="text",
                        label="Username",
                        required=True,
                        priority=10,
                        validation_rules=[
                            ValidationRule(type="minLength", value=3, message="Min 3 chars"),
                            ValidationRule(type="maxLength", value=30, message="Max 30 chars"),
                            ValidationRule(type="pattern", value="^[a-zA-Z0-9_]+$", message="Alphanumeric + underscore only"),
                        ],
                        data_hints=DataHints(
                            valid_examples=["john_doe", "alice123"],
                            invalid_examples=["ab", "user name", "user@name"],
                        ),
                    ),
                    Field(
                        name="password",
                        type="password",
                        label="Password",
                        required=True,
                        priority=10,
                        validation_rules=[
                            ValidationRule(type="minLength", value=8, message="Min 8 chars"),
                            ValidationRule(type="maxLength", value=128, message="Max 128 chars"),
                            ValidationRule(
                                type="pattern",
                                value="^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&])",
                                message="Must have upper, lower, number, special char",
                            ),
                        ],
                        data_hints=DataHints(
                            valid_examples=["Secure@123", "P@ssw0rd!"],
                            invalid_examples=["password", "12345678", "short"],
                        ),
                    ),
                ],
            ),
            Section(
                id="metadata",
                name="Metadata",
                order=4,
                fields=[
                    Field(
                        name="termsAccepted",
                        type="checkbox",
                        label="Accept Terms and Conditions",
                        required=True,
                        priority=6,
                        data_hints=DataHints(
                            valid_examples=["true"],
                            invalid_examples=["false"],
                        ),
                    ),
                    Field(
                        name="newsletter",
                        type="checkbox",
                        label="Subscribe to Newsletter",
                        required=False,
                        priority=2,
                        data_hints=DataHints(
                            valid_examples=["true", "false"],
                        ),
                    ),
                ],
            ),
        ],
        goal_conditions=[
            GoalCondition(type="status_code", value="201"),
            GoalCondition(type="url_contains", value="/success"),
        ],
        astar_config=AStarConfig(
            max_iterations=500,
            heuristic_weight=1.2,
            allow_optional=False,
            timeout_ms=15000,
        ),
    )


REGISTRATION_API_SCHEMA = get_registration_api_schema()
