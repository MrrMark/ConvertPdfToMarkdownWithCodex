from __future__ import annotations

from pdf2md.gui_presets import (
    ASSETLESS_TECHNICAL_SPEC_RAG_PRESET,
    apply_preset_to_options,
    normalize_preset,
    preset_allows_custom_options,
    preset_display_name,
    preset_editable_fields,
)
from pdf2md.gui_runner import GuiConversionOptions
from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode


def test_gui_preset_display_names_are_localized() -> None:
    assert preset_display_name("ko", "preserve") == "기본 모드(원본 유지)"
    assert preset_display_name("ko", "technical_spec_rag") == "기술 스펙 RAG"
    assert preset_display_name("ko", "technical_spec_rag_visual") == "기술 스펙 Visual RAG"
    assert preset_display_name("ko", ASSETLESS_TECHNICAL_SPEC_RAG_PRESET) == "이미지 업로드 불가 RAG 대응"
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
    assert options.rag_profile == "preserve"
    assert options.confidential_safe_mode is False
    assert options.force_ocr is False
    assert options.keep_page_markers is False
    assert options.remove_header_footer is False
    assert options.repair_hyphenation is False
    assert options.figure_crop_fallback is False
    assert options.retrieval_chunk_max_tokens == 512
    assert options.retrieval_tokenizer == "char"
    assert options.rag_contextual_embedding_text is False
    assert options.rag_merge_sibling_text_chunks is False
    assert options.rag_chunk_relationship_metadata is False
    assert options.rag_figure_text_chunks is False
    assert options.figure_region_ocr is False
    assert options.rag_generated_figure_descriptions is False
    assert options.figure_description_backend == "local-vlm"
    assert options.figure_structure_extraction is False
    assert options.skip_existing is True


def test_rag_optimized_preset_enables_sidecar_options_without_force_ocr() -> None:
    current = GuiConversionOptions(
        pages="2",
        password="pw",
        ocr_lang="eng",
        force_ocr=True,
        domain_adapter=DomainAdapterMode.NVME.value,
    )

    options = apply_preset_to_options("rag_optimized", current)

    assert options.pages == "2"
    assert options.password == "pw"
    assert options.ocr_lang == "eng"
    assert options.image_mode == ImageMode.REFERENCED.value
    assert options.table_mode == TableMode.AUTO.value
    assert options.rag_table_output == RagTableOutputMode.BOTH.value
    assert options.rag_profile == "rag_optimized"
    assert options.domain_adapter == DomainAdapterMode.NONE.value
    assert options.keep_page_markers is True
    assert options.remove_header_footer is True
    assert options.repair_hyphenation is True
    assert options.retrieval_chunk_max_tokens == 512
    assert options.retrieval_tokenizer == "regex"
    assert options.rag_contextual_embedding_text is True
    assert options.rag_merge_sibling_text_chunks is True
    assert options.rag_chunk_relationship_metadata is True
    assert options.rag_figure_text_chunks is False
    assert options.figure_region_ocr is False
    assert options.rag_generated_figure_descriptions is False
    assert options.figure_structure_extraction is False
    assert options.force_ocr is False
    assert options.confidential_safe_mode is False


def test_purpose_specific_rag_presets_apply_expected_option_matrix() -> None:
    technical = apply_preset_to_options(
        "technical_spec_rag",
        GuiConversionOptions(force_ocr=True, domain_adapter=DomainAdapterMode.NVME.value),
    )
    confidential = apply_preset_to_options("confidential_rag", GuiConversionOptions())
    sidecar = apply_preset_to_options("preserve_with_sidecars", GuiConversionOptions(remove_header_footer=True))
    visual = apply_preset_to_options(
        "technical_spec_rag_visual",
        GuiConversionOptions(force_ocr=True, domain_adapter=DomainAdapterMode.OCP.value),
    )

    assert technical.rag_profile == "technical_spec_rag"
    assert technical.rag_table_output == RagTableOutputMode.BOTH.value
    assert technical.domain_adapter == DomainAdapterMode.NVME.value
    assert technical.force_ocr is False
    assert technical.remove_header_footer is True
    assert technical.repair_hyphenation is True
    assert technical.retrieval_tokenizer == "regex"
    assert technical.rag_contextual_embedding_text is True
    assert technical.rag_merge_sibling_text_chunks is True
    assert technical.rag_chunk_relationship_metadata is True
    assert technical.rag_figure_text_chunks is False
    assert technical.figure_region_ocr is False
    assert technical.rag_generated_figure_descriptions is False
    assert technical.figure_description_backend == "local-vlm"
    assert technical.figure_structure_extraction is False

    assert visual.rag_profile == "technical_spec_rag_visual"
    assert visual.image_mode == ImageMode.REFERENCED.value
    assert visual.rag_table_output == RagTableOutputMode.BOTH.value
    assert visual.domain_adapter == DomainAdapterMode.OCP.value
    assert visual.force_ocr is False
    assert visual.retrieval_tokenizer == "regex"
    assert visual.rag_contextual_embedding_text is True
    assert visual.rag_merge_sibling_text_chunks is True
    assert visual.rag_chunk_relationship_metadata is True
    assert visual.rag_figure_text_chunks is True
    assert visual.figure_region_ocr is True
    assert visual.rag_generated_figure_descriptions is True
    assert visual.figure_description_backend == "local-vlm"
    assert visual.figure_structure_extraction is True

    assetless = apply_preset_to_options(
        ASSETLESS_TECHNICAL_SPEC_RAG_PRESET,
        GuiConversionOptions(domain_adapter=DomainAdapterMode.MANUAL.value, manual_domain_adapter_label="Customer A"),
    )
    assert assetless.rag_profile == "technical_spec_rag_visual"
    assert assetless.image_mode == ImageMode.PLACEHOLDER.value
    assert assetless.rag_table_output == RagTableOutputMode.BOTH.value
    assert assetless.domain_adapter == DomainAdapterMode.MANUAL.value
    assert assetless.manual_domain_adapter_label == "Customer A"
    assert assetless.rag_figure_text_chunks is True
    assert assetless.figure_region_ocr is True
    assert assetless.rag_generated_figure_descriptions is True
    assert assetless.figure_structure_extraction is True

    assert confidential.confidential_safe_mode is True
    assert confidential.rag_profile == "confidential_rag"
    assert confidential.rag_table_output == RagTableOutputMode.JSONL.value
    assert confidential.retrieval_tokenizer == "regex"
    assert confidential.rag_chunk_relationship_metadata is True

    assert sidecar.rag_table_output == RagTableOutputMode.JSONL.value
    assert sidecar.rag_profile == "preserve_with_sidecars"
    assert sidecar.remove_header_footer is False
    assert sidecar.repair_hyphenation is False
    assert sidecar.rag_contextual_embedding_text is False
    assert sidecar.rag_merge_sibling_text_chunks is False
    assert sidecar.rag_chunk_relationship_metadata is True
    assert sidecar.rag_figure_text_chunks is False
    assert sidecar.rag_generated_figure_descriptions is False


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
    assert rag_fields["rag_contextual_embedding_text"] is False
    assert rag_fields["rag_merge_sibling_text_chunks"] is False
    assert rag_fields["rag_chunk_relationship_metadata"] is False
    assert rag_fields["rag_figure_text_chunks"] is False
    assert rag_fields["figure_region_ocr"] is False
    assert rag_fields["rag_generated_figure_descriptions"] is False
    assert rag_fields["figure_description_backend"] is False
    assert rag_fields["figure_structure_extraction"] is False
    assert rag_fields["remove_header_footer"] is False
    assert rag_fields["domain_adapter"] is False
    assert preset_editable_fields("technical_spec_rag")["retrieval_tokenizer"] is False
    assert preset_editable_fields("technical_spec_rag")["domain_adapter"] is True
    assert preset_editable_fields("technical_spec_rag_visual")["domain_adapter"] is True
    assert preset_editable_fields(ASSETLESS_TECHNICAL_SPEC_RAG_PRESET)["domain_adapter"] is True
    assert preset_editable_fields(ASSETLESS_TECHNICAL_SPEC_RAG_PRESET)["manual_domain_adapter_label"] is True
    assert preset_editable_fields(ASSETLESS_TECHNICAL_SPEC_RAG_PRESET)["manual_domain_adapter_keywords"] is True
    assert custom_fields["image_mode"] is True
    assert custom_fields["page_workers"] is True
    assert custom_fields["retrieval_tokenizer"] is True
    assert custom_fields["figure_description_backend"] is True
    assert custom_fields["figure_structure_extraction"] is True
    assert custom_fields["debug"] is True
    assert custom_fields["verbose"] is True
    assert custom_fields["skip_existing"] is True
