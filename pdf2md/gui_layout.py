from __future__ import annotations

from dataclasses import dataclass


GUI_WINDOW_MIN_SIZE: tuple[int, int] = (760, 560)
GUI_CONTROL_WRAP_LENGTH = 220
GUI_STATUS_WRAP_LENGTH = 680


@dataclass(frozen=True)
class GuiLayoutSection:
    key: str
    text_keys: tuple[str, ...]
    scrollable: bool = True
    wraps_text: bool = False


GUI_LAYOUT_SECTIONS: tuple[GuiLayoutSection, ...] = (
    GuiLayoutSection(
        key="language",
        text_keys=("language", "language_ko", "language_en"),
    ),
    GuiLayoutSection(
        key="preset",
        text_keys=(
            "preset",
            "preset_preserve",
            "preset_rag_optimized",
            "preset_technical_spec_rag",
            "preset_assetless_technical_spec_rag",
            "preset_confidential_rag",
            "preset_preserve_with_sidecars",
            "preset_custom",
        ),
        wraps_text=True,
    ),
    GuiLayoutSection(
        key="input",
        text_keys=("input", "pdf_file", "pdf_folder", "browse"),
    ),
    GuiLayoutSection(
        key="output_folder",
        text_keys=("output_folder", "browse"),
    ),
    GuiLayoutSection(
        key="options",
        text_keys=(
            "options",
            "pages",
            "password",
            "ocr_lang",
            "image",
            "table",
            "rag_tables",
            "domain",
            "manual_domain_adapter_label",
            "manual_domain_adapter_keywords",
            "previous_corpus_manifest",
            "reuse_unchanged",
            "browse",
        ),
        wraps_text=True,
    ),
    GuiLayoutSection(
        key="flags",
        text_keys=(
            "flags",
            "skip_existing",
            "confidential_safe",
            "force_ocr",
            "page_markers",
            "remove_header_footer",
            "dedupe_images",
            "repair_hyphenation",
            "figure_crop_fallback",
            "rag_figure_text_chunks",
        ),
        wraps_text=True,
    ),
    GuiLayoutSection(
        key="expert_options",
        text_keys=("expert_options", "page_workers", "debug", "verbose", "import_profile", "export_profile"),
        wraps_text=True,
    ),
    GuiLayoutSection(
        key="commands",
        text_keys=("start_conversion", "cancel", "open_output_folder", "help", "clear_recent"),
        wraps_text=True,
    ),
    GuiLayoutSection(
        key="progress",
        text_keys=(
            "ready",
            "conversion_starting",
            "batch_conversion_starting",
            "batch_progress",
            "page_progress",
            "single_complete_percent",
        ),
        wraps_text=True,
    ),
    GuiLayoutSection(
        key="results",
        text_keys=("results", "document", "status", "warnings", "retry", "markdown", "report"),
    ),
    GuiLayoutSection(
        key="result_actions",
        text_keys=(
            "open_markdown",
            "open_report",
            "open_manifest",
            "open_assets",
            "open_output_folder",
            "open_corpus_manifest",
            "open_corpus_diff",
            "open_requirement_impact",
        ),
        wraps_text=True,
    ),
)


def gui_layout_text_keys() -> tuple[str, ...]:
    """Return visible GUI text keys covered by layout metadata."""
    keys: list[str] = []
    seen: set[str] = set()
    for section in GUI_LAYOUT_SECTIONS:
        for key in section.text_keys:
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return tuple(keys)


def gui_wrapping_text_keys() -> tuple[str, ...]:
    """Return GUI text keys that should tolerate longer localized labels."""
    keys: list[str] = []
    seen: set[str] = set()
    for section in GUI_LAYOUT_SECTIONS:
        if not section.wraps_text:
            continue
        for key in section.text_keys:
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return tuple(keys)


def gui_scrollable_section_keys() -> tuple[str, ...]:
    """Return section keys that live inside the scrollable GUI body."""
    return tuple(section.key for section in GUI_LAYOUT_SECTIONS if section.scrollable)
