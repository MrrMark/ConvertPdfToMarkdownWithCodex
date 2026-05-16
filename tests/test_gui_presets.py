from __future__ import annotations

from pdf2md.gui_presets import (
    apply_preset_to_options,
    normalize_preset,
    preset_allows_custom_options,
    preset_display_name,
    preset_editable_fields,
)
from pdf2md.gui_runner import GuiConversionOptions
from pdf2md.models import ImageMode, RagTableOutputMode, TableMode


def test_gui_preset_display_names_are_localized() -> None:
    assert preset_display_name("ko", "preserve") == "기본 모드(원본 유지)"
    assert preset_display_name("en", "custom") == "Optimize Options"
    assert normalize_preset(None) == "preserve"
    assert normalize_preset("unknown") == "preserve"


def test_preserve_preset_is_conservative_and_keeps_document_inputs() -> None:
    current = GuiConversionOptions(
        pages="1-3",
        password="secret",
        ocr_lang="kor+eng",
        confidential_safe_mode=True,
        force_ocr=True,
        keep_page_markers=True,
        remove_header_footer=True,
        repair_hyphenation=True,
        figure_crop_fallback=True,
        skip_existing=True,
    )

    options = apply_preset_to_options("preserve", current)

    assert options.pages == "1-3"
    assert options.password == "secret"
    assert options.ocr_lang == "kor+eng"
    assert options.image_mode == ImageMode.REFERENCED.value
    assert options.table_mode == TableMode.AUTO.value
    assert options.rag_table_output == RagTableOutputMode.NONE.value
    assert options.confidential_safe_mode is False
    assert options.force_ocr is False
    assert options.keep_page_markers is False
    assert options.remove_header_footer is False
    assert options.repair_hyphenation is False
    assert options.figure_crop_fallback is False
    assert options.skip_existing is True


def test_rag_optimized_preset_enables_sidecar_options_without_force_ocr() -> None:
    current = GuiConversionOptions(pages="2", password="pw", ocr_lang="eng", force_ocr=True)

    options = apply_preset_to_options("rag_optimized", current)

    assert options.pages == "2"
    assert options.password == "pw"
    assert options.ocr_lang == "eng"
    assert options.image_mode == ImageMode.REFERENCED.value
    assert options.table_mode == TableMode.AUTO.value
    assert options.rag_table_output == RagTableOutputMode.BOTH.value
    assert options.keep_page_markers is True
    assert options.remove_header_footer is True
    assert options.repair_hyphenation is True
    assert options.force_ocr is False
    assert options.confidential_safe_mode is False


def test_custom_preset_preserves_current_options() -> None:
    current = GuiConversionOptions(force_ocr=True, rag_table_output=RagTableOutputMode.JSONL.value)

    assert apply_preset_to_options("custom", current) == current
    assert preset_allows_custom_options("custom") is True
    assert preset_allows_custom_options("preserve") is False


def test_preset_editable_fields_lock_advanced_options_headlessly() -> None:
    preserve_fields = preset_editable_fields("preserve")
    rag_fields = preset_editable_fields("rag_optimized")
    custom_fields = preset_editable_fields("custom")

    for fields in (preserve_fields, rag_fields, custom_fields):
        assert fields["pages"] is True
        assert fields["password"] is True
        assert fields["ocr_lang"] is True

    assert preserve_fields["image_mode"] is False
    assert preserve_fields["page_workers"] is False
    assert preserve_fields["debug"] is False
    assert preserve_fields["verbose"] is False
    assert preserve_fields["skip_existing"] is False
    assert rag_fields["rag_table_output"] is False
    assert rag_fields["remove_header_footer"] is False
    assert custom_fields["image_mode"] is True
    assert custom_fields["page_workers"] is True
    assert custom_fields["debug"] is True
    assert custom_fields["verbose"] is True
    assert custom_fields["skip_existing"] is True
