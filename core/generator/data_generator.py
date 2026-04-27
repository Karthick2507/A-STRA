"""ASTRA data generator - generates valid/invalid test data per field type."""
from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from schemas.field_schema import DataHints, ResolvedField, ValidationRule
from utils.logger import logger


@dataclass
class GeneratedValue:
    field_name: str
    value: Any
    is_valid: bool
    strategy: str
    boundary_type: Optional[str] = None


@dataclass
class FieldDataSet:
    field_name: str
    valid_values: List[Any] = field(default_factory=list)
    invalid_values: List[Any] = field(default_factory=list)
    boundary_values: List[GeneratedValue] = field(default_factory=list)


class DataGenerator:
    def __init__(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            random.seed(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_for_field(self, f: ResolvedField) -> FieldDataSet:
        ds = FieldDataSet(field_name=f.name)

        if f.data_hints and f.data_hints.valid_examples:
            ds.valid_values = list(f.data_hints.valid_examples)
        else:
            ds.valid_values = [self._generate_by_type(f.type, f.name, valid=True)]

        if f.data_hints and f.data_hints.invalid_examples:
            ds.invalid_values = list(f.data_hints.invalid_examples)
        else:
            ds.invalid_values = [self._generate_by_type(f.type, f.name, valid=False)]

        ds.boundary_values = self._generate_boundary_values(f)
        return ds

    def generate_for_all_fields(self, fields: List[ResolvedField]) -> Dict[str, FieldDataSet]:
        return {f.name: self.generate_for_field(f) for f in fields}

    def pick_valid(self, f: ResolvedField) -> Any:
        ds = self.generate_for_field(f)
        return ds.valid_values[0] if ds.valid_values else ""

    def pick_invalid(self, f: ResolvedField) -> Any:
        ds = self.generate_for_field(f)
        return ds.invalid_values[0] if ds.invalid_values else "INVALID"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _generate_by_type(self, field_type: str, name: str, valid: bool) -> Any:
        generators = {
            "email": self._email,
            "password": self._password,
            "tel": self._phone,
            "number": self._number,
            "url": self._url,
            "date": self._date,
            "checkbox": self._checkbox,
            "select": self._select,
            "radio": self._radio,
            "textarea": self._textarea,
        }
        gen = generators.get(field_type, self._text)
        return gen(name=name, valid=valid)

    def _text(self, name: str = "", valid: bool = True, min_len: int = 3, max_len: int = 20) -> str:
        if not valid:
            return "" if random.random() < 0.5 else "A"  # too short
        length = random.randint(min_len, max_len)
        return "".join(random.choices(string.ascii_letters, k=length)).capitalize()

    def _email(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return random.choice(["notanemail", "missing@tld", "@nodomain.com", "double@@domain.com"])
        username = "".join(random.choices(string.ascii_lowercase, k=8))
        domain = random.choice(["example.com", "test.org", "mail.net"])
        return f"{username}@{domain}"

    def _password(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return random.choice(["short", "alllowercase", "12345678", "ALLUPPER"])
        chars = string.ascii_letters + string.digits + "@$!%*?&"
        base = "".join(random.choices(chars, k=10))
        return f"Aa1@{base}"

    def _phone(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return random.choice(["123", "abcdefghij", "00000"])
        return "+1" + "".join(random.choices(string.digits, k=10))

    def _number(self, name: str = "", valid: bool = True) -> Any:
        if not valid:
            return "notanumber"
        return random.randint(1, 100)

    def _url(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return "not-a-url"
        return f"https://example-{uuid.uuid4().hex[:6]}.com"

    def _date(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return "99/99/9999"
        d = date.today() - timedelta(days=random.randint(365, 9125))
        return d.strftime("%Y-%m-%d")

    def _checkbox(self, name: str = "", valid: bool = True) -> bool:
        return valid

    def _select(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return "INVALID_OPTION"
        return "option1"

    def _radio(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return "INVALID_OPTION"
        return "option1"

    def _textarea(self, name: str = "", valid: bool = True) -> str:
        if not valid:
            return "A"  # too short
        return "Sample textarea content for testing purposes."

    def _generate_boundary_values(self, f: ResolvedField) -> List[GeneratedValue]:
        boundaries: List[GeneratedValue] = []
        for rule in f.validation_rules:
            if rule.type == "minLength":
                min_len = int(rule.value)
                boundaries.append(GeneratedValue(
                    field_name=f.name, value="A" * (min_len - 1),
                    is_valid=False, strategy="boundary", boundary_type="below_min"
                ))
                boundaries.append(GeneratedValue(
                    field_name=f.name, value="A" * min_len,
                    is_valid=True, strategy="boundary", boundary_type="at_min"
                ))
            elif rule.type == "maxLength":
                max_len = int(rule.value)
                boundaries.append(GeneratedValue(
                    field_name=f.name, value="A" * max_len,
                    is_valid=True, strategy="boundary", boundary_type="at_max"
                ))
                boundaries.append(GeneratedValue(
                    field_name=f.name, value="A" * (max_len + 1),
                    is_valid=False, strategy="boundary", boundary_type="above_max"
                ))
        return boundaries
