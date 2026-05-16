from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any, Mapping

from pdf2md.gui_runner import GuiConversionOptions, GuiDiagnostic, GuiDiagnosticError, GuiDiagnosticReport
from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode


GUI_PROFILE_SCHEMA_VERSION = 1
GUI_PROFILE_KIND = "pdf2md_gui_profile"
GUI_PROFILE_DEFAULT_NAME = "custom"
GUI_PROFILE_OPTION_FIELDS: tuple[str, ...] = (
    "pages",
    "image_mode",
    "table_mode",
    "rag_table_output",
    "domain_adapter",
    "confidential_safe_mode",
    "force_ocr",
    "ocr_lang",
    "keep_page_markers",
    "remove_header_footer",
    "dedupe_images",
    "repair_hyphenation",
    "figure_crop_fallback",
    "page_workers",
    "debug",
    "verbose",
    "skip_existing",
)
GUI_PROFILE_FORBIDDEN_FIELDS: tuple[str, ...] = (
    "password",
    "input_path",
    "output_dir",
    "raw_pdf_text",
    "raw_markdown",
    "table_content",
    "image_content",
)
GUI_PROFILE_MAX_PAGE_WORKERS = 64


def gui_profile_payload(options: GuiConversionOptions, *, name: str = GUI_PROFILE_DEFAULT_NAME) -> dict[str, Any]:
    """Return a local-only GUI profile payload without paths, password, or raw document content."""
    option_values = asdict(options)
    return {
        "schema_version": GUI_PROFILE_SCHEMA_VERSION,
        "kind": GUI_PROFILE_KIND,
        "name": name or GUI_PROFILE_DEFAULT_NAME,
        "options": {
            field: option_values[field]
            for field in GUI_PROFILE_OPTION_FIELDS
        },
        "redaction_policy": {
            "stores_input_path": False,
            "stores_output_dir": False,
            "stores_password": False,
            "stores_raw_pdf_text": False,
            "stores_table_content": False,
            "stores_image_content": False,
        },
    }


def validate_gui_profile_payload(payload: object) -> GuiDiagnosticReport:
    """Validate a GUI profile payload and return structured diagnostics."""
    diagnostics: list[GuiDiagnostic] = []
    if not isinstance(payload, Mapping):
        return GuiDiagnosticReport(
            [
                GuiDiagnostic(
                    code="profile_not_object",
                    severity="error",
                    message="GUI profile must be a JSON object.",
                    action="Export a new profile from the GUI or provide a JSON object.",
                )
            ]
        )
    schema_version = payload.get("schema_version")
    if schema_version != GUI_PROFILE_SCHEMA_VERSION:
        diagnostics.append(
            GuiDiagnostic(
                code="profile_schema_unsupported",
                severity="error",
                message=f"Unsupported GUI profile schema version: {schema_version}.",
                action=f"Use schema_version {GUI_PROFILE_SCHEMA_VERSION}.",
            )
        )
    if payload.get("kind") not in (None, GUI_PROFILE_KIND):
        diagnostics.append(
            GuiDiagnostic(
                code="profile_kind_unsupported",
                severity="error",
                message=f"Unsupported GUI profile kind: {payload.get('kind')}.",
                action=f"Use kind {GUI_PROFILE_KIND}.",
            )
        )
    for field in GUI_PROFILE_FORBIDDEN_FIELDS:
        if field in payload:
            diagnostics.append(_forbidden_diagnostic(field))
    raw_options = payload.get("options")
    if not isinstance(raw_options, Mapping):
        diagnostics.append(
            GuiDiagnostic(
                code="profile_options_missing",
                severity="error",
                message="GUI profile must contain an options object.",
                action="Export a new profile from the GUI.",
            )
        )
        return GuiDiagnosticReport(diagnostics)
    for field in GUI_PROFILE_FORBIDDEN_FIELDS:
        if field in raw_options:
            diagnostics.append(_forbidden_diagnostic(field))
    unknown_fields = sorted(str(field) for field in raw_options if str(field) not in GUI_PROFILE_OPTION_FIELDS)
    if unknown_fields:
        diagnostics.append(
            GuiDiagnostic(
                code="profile_unknown_options_ignored",
                severity="warning",
                message=f"Unknown GUI profile options will be ignored: {', '.join(unknown_fields)}.",
                action="Remove unknown fields if this was not intentional.",
            )
        )
    diagnostics.extend(_option_type_diagnostics(raw_options))
    return GuiDiagnosticReport(diagnostics)


def options_from_gui_profile(
    payload: object,
    *,
    base_options: GuiConversionOptions | None = None,
) -> GuiConversionOptions:
    """Return GUI options from a validated profile, preserving fields not stored by profiles."""
    report = validate_gui_profile_payload(payload)
    if report.has_errors:
        raise GuiDiagnosticError(report)
    options = base_options or GuiConversionOptions()
    raw_options = payload.get("options", {}) if isinstance(payload, Mapping) else {}
    updates = {
        field: raw_options[field]
        for field in GUI_PROFILE_OPTION_FIELDS
        if isinstance(raw_options, Mapping) and field in raw_options
    }
    return replace(options, **updates)


def write_gui_profile(path: Path, options: GuiConversionOptions, *, name: str = GUI_PROFILE_DEFAULT_NAME) -> Path:
    """Write a sanitized GUI profile JSON file."""
    payload = gui_profile_payload(options, name=name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_gui_profile(path: Path, *, base_options: GuiConversionOptions | None = None) -> GuiConversionOptions:
    """Load GUI conversion options from a sanitized local profile file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return options_from_gui_profile(payload, base_options=base_options)


def _forbidden_diagnostic(field: str) -> GuiDiagnostic:
    return GuiDiagnostic(
        code="profile_forbidden_field",
        severity="error",
        message=f"GUI profile must not store forbidden field: {field}.",
        action="Remove paths, passwords, and raw document content from the profile.",
    )


def _option_type_diagnostics(options: Mapping[str, object]) -> list[GuiDiagnostic]:
    diagnostics: list[GuiDiagnostic] = []
    _validate_optional_string(options, "pages", diagnostics)
    _validate_string(options, "ocr_lang", diagnostics)
    _validate_enum(options, "image_mode", {mode.value for mode in ImageMode}, diagnostics)
    _validate_enum(options, "table_mode", {mode.value for mode in TableMode}, diagnostics)
    _validate_enum(options, "rag_table_output", {mode.value for mode in RagTableOutputMode}, diagnostics)
    _validate_enum(options, "domain_adapter", {mode.value for mode in DomainAdapterMode}, diagnostics)
    for field in (
        "confidential_safe_mode",
        "force_ocr",
        "keep_page_markers",
        "remove_header_footer",
        "dedupe_images",
        "repair_hyphenation",
        "figure_crop_fallback",
        "debug",
        "verbose",
        "skip_existing",
    ):
        _validate_bool(options, field, diagnostics)
    if "page_workers" in options:
        value = options["page_workers"]
        if not isinstance(value, int) or isinstance(value, bool) or not (1 <= value <= GUI_PROFILE_MAX_PAGE_WORKERS):
            diagnostics.append(
                GuiDiagnostic(
                    code="profile_option_invalid",
                    severity="error",
                    message=f"profile option page_workers must be an integer between 1 and {GUI_PROFILE_MAX_PAGE_WORKERS}.",
                    action="Use a conservative worker count such as 1, 2, or 4.",
                )
            )
    return diagnostics


def _validate_optional_string(options: Mapping[str, object], field: str, diagnostics: list[GuiDiagnostic]) -> None:
    if field in options and options[field] is not None and not isinstance(options[field], str):
        diagnostics.append(_invalid_option_diagnostic(field, "a string or null"))


def _validate_string(options: Mapping[str, object], field: str, diagnostics: list[GuiDiagnostic]) -> None:
    if field in options and not isinstance(options[field], str):
        diagnostics.append(_invalid_option_diagnostic(field, "a string"))


def _validate_bool(options: Mapping[str, object], field: str, diagnostics: list[GuiDiagnostic]) -> None:
    if field in options and not isinstance(options[field], bool):
        diagnostics.append(_invalid_option_diagnostic(field, "a boolean"))


def _validate_enum(
    options: Mapping[str, object],
    field: str,
    values: set[str],
    diagnostics: list[GuiDiagnostic],
) -> None:
    if field in options and options[field] not in values:
        diagnostics.append(_invalid_option_diagnostic(field, "one of: " + ", ".join(sorted(values))))


def _invalid_option_diagnostic(field: str, expected: str) -> GuiDiagnostic:
    return GuiDiagnostic(
        code="profile_option_invalid",
        severity="error",
        message=f"profile option {field} must be {expected}.",
        action="Export a fresh profile or edit the profile to match the documented option type.",
    )
