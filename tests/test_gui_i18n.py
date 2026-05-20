from __future__ import annotations

from pdf2md.gui_i18n import GUI_TEXT_TRACKING_KEYS, catalog_keys, missing_catalog_keys, normalize_language, translate


def test_gui_i18n_uses_korean_as_default_language() -> None:
    assert normalize_language(None) == "ko"
    assert normalize_language("fr") == "ko"
    assert translate("ko", "start_conversion") == "변환 시작"
    assert translate("ko", "preset_preserve") == "기본 모드(원본 유지)"


def test_gui_i18n_supports_english_catalog() -> None:
    assert normalize_language("en") == "en"
    assert translate("en", "start_conversion") == "Start conversion"
    assert translate("en", "preset_rag_optimized") == "RAG optimized"
    assert translate("en", "preset_technical_spec_rag") == "Technical spec RAG"


def test_gui_i18n_formats_placeholders_and_falls_back() -> None:
    assert translate("ko", "batch_progress", current=2, total=10, percent=20, document="a.pdf", status="success") == (
        "배치 2/10 (20%) a.pdf: success"
    )
    assert translate("ko", "page_progress", current=1, total=3, percent=33, page=1) == "페이지 1/3 (33%) 1쪽"
    assert translate("ko", "conversion_finished_percent", percent="100%") == "변환 완료 (100%)"
    assert translate("ko", "reuse_unchanged") == "변경 없는 문서 재사용"
    assert translate("en", "open_corpus_diff") == "Open Corpus Diff"
    assert translate("ko", "missing_key") == "missing_key"
    assert translate("unknown", "start_conversion") == "변환 시작"


def test_gui_i18n_catalog_covers_tracked_visible_text_keys() -> None:
    assert len(GUI_TEXT_TRACKING_KEYS) == len(set(GUI_TEXT_TRACKING_KEYS))
    assert missing_catalog_keys() == {"ko": (), "en": ()}
    assert "preset_custom" in catalog_keys("ko")
    assert "preset_custom" in catalog_keys("en")
    assert "preset_confidential_rag" in catalog_keys("ko")
