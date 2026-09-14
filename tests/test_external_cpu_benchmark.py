"""External benchmarks must preserve version, availability and quality boundaries."""

import json
from pathlib import Path

import pytest

from scripts import benchmark_external_cpu as external
from scripts import benchmark_fair_comparison as fair
from scripts.benchmark_q157_corpus import collect_case, public_summary, token_smoke


def test_version_mismatch_prevents_conversion(monkeypatch, tmp_path: Path):
    source = tmp_path / "input.pdf"
    source.write_bytes(b"test source")
    monkeypatch.setattr(fair.importlib.metadata, "version", lambda name: "0.0.0")
    report = fair.engine_worker({"engine": "pymupdf", "input_pdf": str(source), "threads": 1,
                                 "expected_package": "pymupdf4llm", "expected_version": "1.27.2.2"})
    assert report["status"] == "unavailable"
    assert report["unavailable_reason"] == "pinned_version_mismatch"
    assert report["runs"] == []


def test_marker_missing_runtime_does_not_disable_ocr(monkeypatch):
    monkeypatch.setattr(external.shutil, "which", lambda name: None)
    with pytest.raises(external.ExternalUnavailable, match="llama_server_missing"):
        external.prepare_external("marker", {"threads": 1})


def test_box_counts_ignore_text_and_metadata():
    chunks = [{"text": "table table picture", "page_boxes": [
        {"class": "table"}, {"class": "text"}, {"class": "picture"},
    ]}, {"page_boxes": []}]
    assert external.chunk_counts(chunks) == {"pages": 2, "tables": 1, "pictures": 1}


def test_token_smoke_is_not_a_structure_score():
    truth = {"checks": [{"check_id": "cell", "kind": "table_cell", "tokens": ["A_B", "0h"]}]}
    result = token_smoke("0h appears elsewhere A_B", truth)
    assert result["all_selected_tokens_present"]
    assert result["page_cell_order_and_geometry"] == "not_evaluated"
    assert not token_smoke("A_B only", truth)["all_selected_tokens_present"]


def test_collect_refuses_different_source_truth(tmp_path: Path):
    (tmp_path / "fair_benchmark_report.json").write_text(json.dumps({"source_sha256": "a" * 64}))
    with pytest.raises(ValueError, match="truth hash mismatch"):
        collect_case(tmp_path, {"input_sha256": "b" * 64})


def test_full_document_uses_original_bytes(monkeypatch, tmp_path: Path):
    from test_fair_benchmark import arguments
    from types import SimpleNamespace

    args = arguments(tmp_path, pages=None)

    def worker(command, **kwargs):
        request = json.loads(Path(command[-3]).read_text())
        assert Path(request["input_pdf"]).read_bytes() == args.input_pdf.read_bytes()
        Path(command[-1]).write_text(json.dumps({
            "engine": "native", "status": "unavailable", "input_sha256": fair.file_hash(args.input_pdf),
        }))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(fair.subprocess, "run", worker)
    report = fair.run_benchmark(args)
    assert report["method"]["input_preparation_method"] == "byte_copy"
    assert report["source_sha256"] == report["slice_sha256"]


def test_public_summary_omits_source_and_paths():
    summary = {"purpose": "test", "quality_scope": "smoke", "cases": {"test": {
        "source_sha256": "a" * 64, "slice_sha256": "a" * 64, "source_pages": [1],
        "method": {}, "timing_samples_complete": True, "engines": [{
            "engine": "native", "status": "success", "effective_options": {"private_path": "/private/source"},
            "runs": [{"phase": "cold", "status": "success", "index": 0,
                      "convert_export_write_seconds": 1, "source_text": "private text"}],
        }],
    }}}
    rendered = json.dumps(public_summary(summary))
    assert "private" not in rendered
    assert "convert_export_write_seconds" in rendered
