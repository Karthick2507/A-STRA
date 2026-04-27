"""ASTRA schema reconciler - live DOM sync to keep schemas current."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from schemas.field_schema import Field, FieldSchema, Section
from utils.logger import logger


@dataclass
class LiveField:
    name: str
    type: str
    selector: str
    visible: bool
    enabled: bool
    required: bool
    placeholder: Optional[str] = None
    label: Optional[str] = None


@dataclass
class ReconcileReport:
    added_fields: List[str] = field(default_factory=list)
    removed_fields: List[str] = field(default_factory=list)
    updated_fields: List[str] = field(default_factory=list)
    unchanged_fields: List[str] = field(default_factory=list)
    total_live_fields: int = 0
    total_schema_fields: int = 0


class SchemaReconciler:
    def __init__(self, page: Page, schema: FieldSchema) -> None:
        self.page = page
        self.schema = schema

    def reconcile(self) -> tuple[FieldSchema, ReconcileReport]:
        logger.preflight("SchemaReconciler: scanning live page...")
        live_fields = self._scan_live_page()
        report = self._compare_fields(live_fields)
        reconciled = self._build_reconciled_schema(live_fields, report)
        logger.preflight(
            f"Reconcile complete: +{len(report.added_fields)} "
            f"-{len(report.removed_fields)} ~{len(report.updated_fields)}"
        )
        return reconciled, report

    def _scan_live_page(self) -> List[LiveField]:
        live: List[LiveField] = []
        selectors = [
            "input:not([type=hidden]):not([type=submit]):not([type=button])",
            "select",
            "textarea",
        ]
        for sel in selectors:
            elements = self.page.query_selector_all(sel)
            for el in elements:
                try:
                    name = (
                        el.get_attribute("name")
                        or el.get_attribute("id")
                        or el.get_attribute("data-testid")
                        or ""
                    )
                    if not name:
                        continue
                    el_type = el.get_attribute("type") or el.evaluate("e => e.tagName.toLowerCase()")
                    css_sel = (
                        f"[name='{name}']"
                        if el.get_attribute("name")
                        else f"#{el.get_attribute('id')}"
                    )
                    live.append(
                        LiveField(
                            name=name,
                            type=el_type,
                            selector=css_sel,
                            visible=el.is_visible(),
                            enabled=el.is_enabled(),
                            required=el.get_attribute("required") is not None,
                            placeholder=el.get_attribute("placeholder"),
                        )
                    )
                except Exception:
                    continue
        return live

    def _compare_fields(self, live_fields: List[LiveField]) -> ReconcileReport:
        schema_names = {
            f.name
            for section in self.schema.sections
            for f in section.fields
        }
        live_names = {lf.name for lf in live_fields}

        return ReconcileReport(
            added_fields=list(live_names - schema_names),
            removed_fields=list(schema_names - live_names),
            updated_fields=[
                lf.name
                for lf in live_fields
                if lf.name in schema_names
                and not self._field_matches(lf)
            ],
            unchanged_fields=list(live_names & schema_names),
            total_live_fields=len(live_fields),
            total_schema_fields=len(schema_names),
        )

    def _field_matches(self, live: LiveField) -> bool:
        for section in self.schema.sections:
            for f in section.fields:
                if f.name == live.name:
                    return f.type == live.type and f.required == live.required
        return False

    def _build_reconciled_schema(self, live_fields: List[LiveField], report: ReconcileReport) -> FieldSchema:
        import copy
        reconciled = copy.deepcopy(self.schema)

        # Build lookup of live fields
        live_map: Dict[str, LiveField] = {lf.name: lf for lf in live_fields}

        # Update existing sections
        for section in reconciled.sections:
            # Remove fields not in live DOM
            section.fields = [
                f for f in section.fields if f.name not in report.removed_fields
            ]
            # Update changed fields
            for f in section.fields:
                if f.name in report.updated_fields and f.name in live_map:
                    lf = live_map[f.name]
                    f.type = lf.type
                    f.required = lf.required
                    if lf.selector:
                        f.selector = lf.selector

        # Add new fields discovered in live DOM to a reconciled section
        if report.added_fields:
            new_fields = [
                Field(
                    name=name,
                    type=live_map[name].type,
                    selector=live_map[name].selector,
                    required=live_map[name].required,
                    priority=3,
                )
                for name in report.added_fields
                if name in live_map
            ]
            existing_ids = {s.id for s in reconciled.sections}
            if "reconciled" not in existing_ids:
                reconciled.sections.append(
                    Section(id="reconciled", name="Reconciled Fields", fields=new_fields, order=99)
                )
            else:
                for s in reconciled.sections:
                    if s.id == "reconciled":
                        s.fields.extend(new_fields)

        return reconciled


def reconcile_ui_schema(page: Page, schema: FieldSchema) -> tuple[FieldSchema, ReconcileReport]:
    return SchemaReconciler(page, schema).reconcile()


def reconcile_api_schema(schema: FieldSchema) -> tuple[FieldSchema, ReconcileReport]:
    """API schemas do not require DOM reconciliation; return schema unchanged."""
    report = ReconcileReport(
        unchanged_fields=[
            f.name
            for section in schema.sections
            for f in section.fields
        ],
        total_schema_fields=sum(len(s.fields) for s in schema.sections),
        total_live_fields=sum(len(s.fields) for s in schema.sections),
    )
    return schema, report
