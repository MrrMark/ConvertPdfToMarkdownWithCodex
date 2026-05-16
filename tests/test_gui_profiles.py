from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf2md.gui_profiles import (
    GUI_PROFILE_KIND,
    GUI_PROFILE_SCHEMA_VERSION,
    gui_profile_payload,
    load_gui_profile,
    options_from_gui_profile,
    validate_gui_profile_payload,
    write_gui_profile,
)
from pdf2md.gui_runner import GuiConversionOptions, GuiDiagnosticError
from pdf2md.models import ImageMode, RagTableOutputMode, TableMode


def test_gui_profile_export_omits_paths_password_and_raw_content(tmp_path: Path) -> None:
    options = GuiConversionOptions(
        pages="1-3",
        password="secret-password",
        image_mode=ImageMode.PLACEHOLDER.value,
        table_mode=TableMode.HTML.value,
        rag_table_output=RagTableOutputMode.JSONL.value,
        force_ocr=True,
        ocr_lang="kor+eng",
        page_workers=4,
        debug=True,
        verbose=True,
    )

    payload = gui_profile_payload(options, name="qa")
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    path = write_gui_profile(tmp_path / "profile.json", options, name="qa")
    written = path.read_text(encoding="utf-8")

    assert payload["schema_version"] == GUI_PROFILE_SCHEMA_VERSION
    assert payload["kind"] == GUI_PROFILE_KIND
    assert payload["options"]["page_workers"] == 4
    assert payload["options"]["debug"] is True
    assert payload["options"]["verbose"] is True
    assert "password" not in payload["options"]
    assert "secret-password" not in serialized
    assert "input_path" not in payload["options"]
    assert "output_dir" not in payload["options"]
    assert "raw_pdf_text" not in payload["options"]
    assert str(tmp_path) not in written


def test_gui_profile_import_preserves_password_from_base_options() -> None:
    payload = gui_profile_payload(
        GuiConversionOptions(
            pages="2",
            password="not-exported",
            force_ocr=True,
            page_workers=3,
            debug=True,
            verbose=True,
        )
    )

    options = options_from_gui_profile(
        payload,
        base_options=GuiConversionOptions(password="current-secret", ocr_lang="eng"),
    )

    assert options.pages == "2"
    assert options.password == "current-secret"
    assert options.force_ocr is True
    assert options.page_workers == 3
    assert options.debug is True
    assert options.verbose is True


def test_gui_profile_invalid_payload_returns_structured_diagnostics() -> None:
    payload = {
        "schema_version": 999,
        "kind": "other",
        "input_path": "/Users/example/private.pdf",
        "options": {
            "password": "secret",
            "image_mode": "bad",
            "page_workers": 0,
            "debug": "yes",
        },
    }

    report = validate_gui_profile_payload(payload)

    assert report.has_errors is True
    assert {
        "profile_schema_unsupported",
        "profile_kind_unsupported",
        "profile_forbidden_field",
        "profile_option_invalid",
    } <= {diagnostic.code for diagnostic in report.errors}
    with pytest.raises(GuiDiagnosticError):
        options_from_gui_profile(payload)


def test_gui_profile_unknown_options_are_warnings_and_ignored() -> None:
    payload = gui_profile_payload(GuiConversionOptions(force_ocr=True))
    payload["options"]["future_option"] = True

    report = validate_gui_profile_payload(payload)
    options = options_from_gui_profile(payload)

    assert report.has_errors is False
    assert [diagnostic.code for diagnostic in report.warnings] == ["profile_unknown_options_ignored"]
    assert options.force_ocr is True
    assert not hasattr(options, "future_option")


def test_gui_profile_load_round_trip(tmp_path: Path) -> None:
    path = write_gui_profile(
        tmp_path / "profile.json",
        GuiConversionOptions(table_mode=TableMode.HTML.value, page_workers=2, skip_existing=True),
    )

    options = load_gui_profile(path)

    assert options.table_mode == TableMode.HTML.value
    assert options.page_workers == 2
    assert options.skip_existing is True
