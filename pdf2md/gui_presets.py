from __future__ import annotations

from dataclasses import replace
from typing import Literal

from pdf2md.gui_i18n import GuiLanguage, translate
from pdf2md.gui_runner import GuiConversionOptions
from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode


GuiOptionPreset = Literal["preserve", "rag_optimized", "custom"]
DEFAULT_GUI_OPTION_PRESET: GuiOptionPreset = "preserve"
SUPPORTED_GUI_OPTION_PRESETS: tuple[GuiOptionPreset, ...] = ("preserve", "rag_optimized", "custom")


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
    if normalized == "rag_optimized":
        return replace(
            current,
            image_mode=ImageMode.REFERENCED.value,
            table_mode=TableMode.AUTO.value,
            rag_table_output=RagTableOutputMode.BOTH.value,
            domain_adapter=DomainAdapterMode.NONE.value,
            force_ocr=False,
            keep_page_markers=True,
            remove_header_footer=True,
            dedupe_images=current.dedupe_images,
            repair_hyphenation=True,
            figure_crop_fallback=current.figure_crop_fallback,
        )
    return replace(
        current,
        image_mode=ImageMode.REFERENCED.value,
        table_mode=TableMode.AUTO.value,
        rag_table_output=RagTableOutputMode.NONE.value,
        domain_adapter=DomainAdapterMode.NONE.value,
        confidential_safe_mode=False,
        force_ocr=False,
        keep_page_markers=False,
        remove_header_footer=False,
        dedupe_images=False,
        repair_hyphenation=False,
        figure_crop_fallback=False,
    )


def preset_allows_custom_options(preset: GuiOptionPreset | str) -> bool:
    """Return whether detailed conversion options should be user-editable."""
    return normalize_preset(str(preset)) == "custom"
