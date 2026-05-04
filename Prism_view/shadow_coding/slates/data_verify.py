"""
data_verify slate — corporate template for data verification / assertion style.

Drop your real corporate data-verify file here.
PRISM will parse the style and apply it when generating {entity}_Data.json and
data assertion helpers.

Role: data_verify → drives {entity}_Data.json + assertion helpers
"""
from __future__ import annotations

import logging

from typing import Any, Dict

logger = logging.getLogger(__name__)


class ExampleDataVerify:
    """Corporate data verification helper."""

    def verify_field(self, actual: Any, expected: Any, field_name: str) -> None:
        logger.info(f"Verifying field '{field_name}': expected={expected}, actual={actual}")
        assert actual == expected, f"Field '{field_name}' mismatch: expected {expected}, got {actual}"

    def verify_response(self, response: Dict[str, Any], schema: Dict[str, Any]) -> None:
        logger.info(f"Verifying response against schema")
        for key in schema:
            assert key in response, f"Missing key '{key}' in response"
