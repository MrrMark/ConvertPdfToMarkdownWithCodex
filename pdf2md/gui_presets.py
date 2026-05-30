from __future__ import annotations

from dataclasses import replace
from typing import Literal

from pdf2md.gui_i18n import GuiLanguage, translate
from pdf2md.gui_runner import GuiConversionOptions
from pdf2md.rag_profiles import SUPPORTED_RAG_PURPOSE_PROFILES, rag_profile_options


GuiOptionPreset = Literal[
    "preserve",
    "rag_optimized",
    "technical_spec_rag",
    "confidential_rag",
    "preserve_with_sidecars",
    "custom",
]
DEFAULT_GUI_OPTION_PRESET: GuiOptionPreset = "preserve"
SUPPORTED_GUI_OPTION_PRESETS: tuple[GuiOptionPreset, ...] = (*SUPPORTED_RAG_PURPOSE_PROFILES, "custom")
GUI_ALWAYS_EDITABLE_OPTION_FIELDS: tuple[str, ...] = ("pages", "password", "ocr_lang")
GUI_PRESET_LOCKED_OPTION_FIELDS: tuple[str, ...] = (
    "image_mode",
    "table_mode",
    "rag_table_output",
    "domain_adapter",
    "confidential_safe_mode",
    "force_ocr",
    "keep_page_markers",
    "remove_header_footer",
    "dedupe_images",
    "repair_hyphenation",
    "figure_crop_fallback",
    "retrieval_chunk_max_tokens",
    "retrieval_tokenizer",
    "rag_contextual_embedding_text",
    "rag_merge_sibling_text_chunks",
    "rag_chunk_relationship_metadata",
    "page_workers",
    "debug",
    "verbose",
    "skip_existing",
)


def normalize_preset(value: str | None) -> GuiOptionPreset:
    """Return a supported GUI preset, defaulting to conservative preservation."""
    if value in SUPPORTED_GUI_OPTION_PRESETS:
        return value
    return DEFAULT_GUI_OPTION_PRESET


def preset_display_name(language: GuiLanguage | str, preset: GuiOptionPreset | str) -> str:
    """Return the localized display name for a GUI option preset."""
    normalized = normalize_preset(str(preset))
    return translate(language, f"preset_{normalized}")


def apply_preset_to_options(preset: GuiOptionPreset | str, current: GuiConversionOptions) -> GuiConversionOptions:
    """Apply a GUI option preset while preserving document-specific inputs."""
    normalized = normalize_preset(str(preset))
    if normalized == "custom":
        return current
    profile_options = rag_profile_options(normalized)
    dedupe_images = current.dedupe_images if normalized == "rag_optimized" else profile_options.dedupe_images
    figure_crop_fallback = (
        current.figure_crop_fallback if normalized == "rag_optimized" else profile_options.figure_crop_fallback
    )
    domain_adapter = (
        current.domain_adapter if normalized == "technical_spec_rag" else profile_options.domain_adapter
    )
    return replace(
        current,
        image_mode=profile_options.image_mode,
        table_mode=profile_options.table_mode,
        rag_table_output=profile_options.rag_table_output,
        rag_profile=normalized,
        domain_adapter=domain_adapter,
        confidential_safe_mode=profile_options.confidential_safe_mode,
        force_ocr=profile_options.force_ocr,
        keep_page_markers=profile_options.keep_page_markers,
        remove_header_footer=profile_options.remove_header_footer,
        dedupe_images=dedupe_images,
        repair_hyphenation=profile_options.repair_hyphenation,
        figure_crop_fallback=figure_crop_fallback,
        retrieval_chunk_max_tokens=profile_options.retrieval_chunk_max_tokens,
        retrieval_tokenizer=profile_options.retrieval_tokenizer,
        rag_contextual_embedding_text=profile_options.rag_contextual_embedding_text,
        rag_merge_sibling_text_chunks=profile_options.rag_merge_sibling_text_chunks,
        rag_chunk_relationship_metadata=profile_options.rag_chunk_relationship_metadata,
    )


def preset_allows_custom_options(preset: GuiOptionPreset | str) -> bool:
    """Return whether detailed conversion options should be user-editable."""
    return normalize_preset(str(preset)) == "custom"


def preset_editable_fields(preset: GuiOptionPreset | str) -> dict[str, bool]:
    """Return the headless editable/locked contract for GUI option controls."""
    advanced_editable = preset_allows_custom_options(preset)
    editable = {field: True for field in GUI_ALWAYS_EDITABLE_OPTION_FIELDS}
    editable.update({field: advanced_editable for field in GUI_PRESET_LOCKED_OPTION_FIELDS})
    if normalize_preset(str(preset)) == "technical_spec_rag":
        editable["domain_adapter"] = True
    return editable
