from __future__ import annotations

from pdf2md.gui_i18n import GUI_TEXT_TRACKING_KEYS
from pdf2md.gui_layout import (
    GUI_CONTROL_WRAP_LENGTH,
    GUI_LAYOUT_SECTIONS,
    GUI_STATUS_WRAP_LENGTH,
    GUI_WINDOW_MIN_SIZE,
    gui_layout_text_keys,
    gui_scrollable_section_keys,
    gui_wrapping_text_keys,
)


def test_gui_layout_metadata_covers_core_visible_sections() -> None:
    section_keys = {section.key for section in GUI_LAYOUT_SECTIONS}

    assert {
        "language",
        "preset",
        "input",
        "options",
        "flags",
        "expert_options",
        "commands",
        "progress",
        "results",
        "result_actions",
    }.issubset(section_keys)
    assert len(section_keys) == len(GUI_LAYOUT_SECTIONS)


def test_gui_layout_text_keys_are_known_i18n_keys() -> None:
    layout_keys = set(gui_layout_text_keys())

    assert layout_keys <= set(GUI_TEXT_TRACKING_KEYS)
    assert {
        "preset_preserve",
        "preset_rag_optimized",
        "expert_options",
        "page_workers",
        "previous_corpus_manifest",
        "reuse_unchanged",
        "open_output_folder",
        "open_assets",
        "open_corpus_diff",
    } <= layout_keys


def test_gui_layout_wraps_long_localized_controls() -> None:
    wrapping_keys = set(gui_wrapping_text_keys())

    assert GUI_CONTROL_WRAP_LENGTH >= 180
    assert GUI_STATUS_WRAP_LENGTH >= GUI_CONTROL_WRAP_LENGTH
    assert {
        "preset_preserve",
        "preset_rag_optimized",
        "preset_custom",
        "open_output_folder",
        "clear_recent",
        "import_profile",
        "export_profile",
        "batch_progress",
        "page_progress",
        "previous_corpus_manifest",
        "reuse_unchanged",
        "open_corpus_manifest",
        "open_corpus_diff",
        "open_requirement_impact",
    } <= wrapping_keys


def test_gui_layout_uses_smaller_scrollable_window_contract() -> None:
    width, height = GUI_WINDOW_MIN_SIZE

    assert width <= 760
    assert height <= 560
    assert {"options", "expert_options", "results", "result_actions"}.issubset(set(gui_scrollable_section_keys()))
