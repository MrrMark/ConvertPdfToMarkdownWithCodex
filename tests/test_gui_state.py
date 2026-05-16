from __future__ import annotations

import json
from pathlib import Path

from pdf2md.gui_runner import GuiDocumentSummary
from pdf2md.gui_state import (
    GuiRecentState,
    GuiStateStore,
    clear_gui_recent_state,
    first_existing_path,
    gui_batch_progress_snapshot,
    gui_document_open_target,
    load_gui_recent_state,
    remember_gui_path,
    save_gui_recent_state,
)


def test_gui_recent_state_round_trips_with_dedupe_and_limit(tmp_path: Path) -> None:
    state_path = tmp_path / "gui_state.json"
    state = GuiRecentState()
    for index in range(7):
        state = remember_gui_path(state, "input_file", tmp_path / f"input-{index}.pdf", max_items=3)
    state = remember_gui_path(state, "input_file", tmp_path / "input-5.pdf", max_items=3)
    state = remember_gui_path(state, "input_folder", tmp_path / "pdfs", max_items=3)
    state = remember_gui_path(state, "output_dir", tmp_path / "output", max_items=3)

    save_gui_recent_state(state, state_path, max_items=3)
    loaded = load_gui_recent_state(state_path)

    assert loaded.recent_input_files == (
        tmp_path / "input-5.pdf",
        tmp_path / "input-6.pdf",
        tmp_path / "input-4.pdf",
    )
    assert loaded.recent_input_folders == (tmp_path / "pdfs",)
    assert loaded.recent_output_dirs == (tmp_path / "output",)
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema_version",
        "recent_input_files",
        "recent_input_folders",
        "recent_output_dirs",
    }
    assert "warning message" not in state_path.read_text(encoding="utf-8")
    assert "table fallback" not in state_path.read_text(encoding="utf-8")


def test_gui_recent_state_falls_back_on_missing_corrupt_or_unknown_schema(tmp_path: Path) -> None:
    state_path = tmp_path / "gui_state.json"

    assert load_gui_recent_state(state_path).is_empty()
    state_path.write_text("{not json", encoding="utf-8")
    assert load_gui_recent_state(state_path).is_empty()
    state_path.write_text(json.dumps({"schema_version": 999, "recent_input_files": ["a.pdf"]}), encoding="utf-8")
    assert load_gui_recent_state(state_path).is_empty()


def test_gui_state_store_clear_removes_recent_paths(tmp_path: Path) -> None:
    state_path = tmp_path / "gui_state.json"
    store = GuiStateStore(state_path, max_items=2)
    state = remember_gui_path(GuiRecentState(), "output_dir", tmp_path / "out", max_items=2)

    store.save(state)
    assert store.load().recent_output_dirs == (tmp_path / "out",)
    cleared = store.clear()

    assert cleared.is_empty()
    assert not state_path.exists()
    assert clear_gui_recent_state(state_path).is_empty()


def test_first_existing_path_ignores_stale_recent_entries(tmp_path: Path) -> None:
    stale = tmp_path / "missing.pdf"
    existing = tmp_path / "existing.pdf"
    existing.write_text("pdf placeholder", encoding="utf-8")

    assert first_existing_path((stale, existing)) == existing
    assert first_existing_path((stale,)) is None


def test_gui_document_open_target_maps_structured_artifact_paths(tmp_path: Path) -> None:
    document = GuiDocumentSummary(
        input_pdf=tmp_path / "input.pdf",
        output_dir=tmp_path / "output",
        status="success",
        exit_code=0,
        markdown_path=tmp_path / "output" / "document.md",
        manifest_path=tmp_path / "output" / "manifest.json",
        report_path=tmp_path / "output" / "report.json",
        assets_dir=tmp_path / "output" / "assets",
    )

    assert gui_document_open_target(document, "markdown") == tmp_path / "output" / "document.md"
    assert gui_document_open_target(document, "report") == tmp_path / "output" / "report.json"
    assert gui_document_open_target(document, "manifest") == tmp_path / "output" / "manifest.json"
    assert gui_document_open_target(document, "assets") == tmp_path / "output" / "assets"
    assert gui_document_open_target(document, "output_dir") == tmp_path / "output"


def test_gui_batch_progress_snapshot_is_document_level_and_clamped(tmp_path: Path) -> None:
    snapshot = gui_batch_progress_snapshot(
        current=2,
        total=5,
        input_pdf=tmp_path / "beta.pdf",
        status="success",
    )

    assert snapshot.current == 2
    assert snapshot.total == 5
    assert snapshot.percent == 40
    assert snapshot.label == "Batch 2/5 beta.pdf: success"

    overflow = gui_batch_progress_snapshot(
        current=9,
        total=5,
        input_pdf=tmp_path / "omega.pdf",
        status="failed",
    )
    assert overflow.current == 5
    assert overflow.percent == 100
