"""Exercise isolated timing, shared inputs and unavailable engine reporting."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from fixtures.pdf_builder import PageSpec, PositionedText, write_pdf
from scripts import benchmark_fair_comparison as bench


def arguments(tmp_path: Path, **changes):
    source = tmp_path / "source.pdf"
    write_pdf(
        source,
        [PageSpec(texts=[PositionedText("First", 50, 700)]), PageSpec(texts=[PositionedText("Second", 50, 700)])],
    )
    values = dict(
        input_pdf=source,
        output_dir=tmp_path / "result",
        pages="2",
        engines=["native"],
        native_profile="preserve",
        domain_adapter="none",
        threads=1,
        docling_python=sys.executable,
        docling_models=None,
        timeout=60,
    )
    return argparse.Namespace(**(values | changes))


def test_native_process_uses_shared_slice_and_cli_profile(tmp_path: Path) -> None:
    args = arguments(tmp_path, native_profile="technical_spec_rag_visual")
    report = bench.run_benchmark(args)
    engine = report["engines"][0]
    assert report["source_pages"] == [2]
    assert engine["pid"] != os.getpid()
    assert engine["input_sha256"] == report["slice_sha256"]
    assert report["timing_samples_complete"]
    assert len(engine["runs"]) == 6 and engine["summary"]["warm_success_count"] == 5
    assert engine["effective_options"]["figure_region_ocr"]
    assert all(r["counts"]["pages"] == 1 for r in engine["runs"])
    assert engine["peak_rss"]["scope"] in {"engine_process_lifetime_excludes_children", "unavailable"}
    markdown = (args.output_dir / "native/cold/document.md").read_text()
    assert "Second" in markdown and "First" not in markdown
    with pytest.raises(FileExistsError):
        bench.run_benchmark(args)


@pytest.mark.parametrize("problem", ["missing", "partial"])
def test_incomplete_warm_samples_have_no_median(problem: str) -> None:
    runs = [dict(phase="warm", status="success", convert_export_write_seconds=float(i)) for i in range(5)]
    if problem == "missing":
        runs.pop()
    else:
        runs[0]["status"] = "partial_success"
    assert bench.summarize_runs(runs)["warm_median_seconds"] is None


def fake_docling(monkeypatch, tmp_path: Path, fail_export=False):
    clock = [0.0]
    monkeypatch.setattr(bench.time, "perf_counter", lambda: clock[0])

    class Options:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def model_dump(self, **kwargs):
            return {"cpu": True, "ocr": "tesseract_cli"}

    class Document:
        tables, pictures, pages = [1, 2], [1], {1: 1}

        def export_to_markdown(self):
            clock[0] += 2
            if fail_export:
                raise RuntimeError("export failed")
            return "source text"

        def export_to_dict(self):
            clock[0] += 4
            return {"table_metadata": {"table_noise": 1}, "image_settings": {}, "pages_info": {}}

    class Converter:
        def __init__(self, **kwargs):
            pass

        def initialize_pipeline(self, format):
            clock[0] += 10

        def convert(self, path):
            clock[0] += 3
            return SimpleNamespace(document=Document(), status=SimpleNamespace(value="success"))

    for key, module in {
        "docling.document_converter": SimpleNamespace(DocumentConverter=Converter, PdfFormatOption=Options),
        "docling.datamodel.base_models": SimpleNamespace(InputFormat=SimpleNamespace(PDF="pdf")),
        "docling.datamodel.pipeline_options": SimpleNamespace(
            PdfPipelineOptions=Options, TesseractCliOcrOptions=Options
        ),
        "docling.datamodel.accelerator_options": SimpleNamespace(AcceleratorOptions=Options),
    }.items():
        monkeypatch.setitem(sys.modules, key, module)
    source = tmp_path / "input.pdf"
    source.write_bytes(b"local input identity")
    models = tmp_path / "models"
    models.mkdir()
    (models / "weight.bin").write_bytes(b"fixed model revision")
    return dict(engine="docling", input_pdf=str(source), models=str(models), output=str(tmp_path / "out"), threads=1)


def test_docling_counts_objects_and_times_export_after_setup(monkeypatch, tmp_path: Path) -> None:
    report = bench.engine_worker(fake_docling(monkeypatch, tmp_path))
    assert report["status"] == "success"
    assert report["setup_seconds"] == 10
    assert all(r["convert_export_write_seconds"] == 9 for r in report["runs"])
    assert report["runs"][0]["counts"] == {"tables": 2, "pictures": 1, "pages": 1}
    assert (tmp_path / "out/cold/document.md").is_file()
    assert (tmp_path / "out/warm-5/document.json").is_file()
    assert report["quality"]["status"] == "not_evaluated"
    assert report["features"]["native_rag_sidecars"] == "unsupported"


def test_export_failure_is_not_successful_timing(monkeypatch, tmp_path: Path) -> None:
    report = bench.engine_worker(fake_docling(monkeypatch, tmp_path, fail_export=True))
    assert report["status"] == "incomplete"
    assert report["summary"]["warm_median_seconds"] is None
    assert all(r["error_type"] == "RuntimeError" for r in report["runs"])


def test_missing_docling_preserves_explicit_unavailability(monkeypatch, tmp_path: Path) -> None:
    args = arguments(tmp_path)
    monkeypatch.setitem(sys.modules, "docling.document_converter", None)
    report = bench.engine_worker(dict(engine="docling", input_pdf=str(args.input_pdf), threads=1))
    assert report["status"] == "unavailable" and report["error"]["stage"] == "import"
    assert report["runs"] == []


@pytest.mark.parametrize("problem", ["timeout", "wrong_hash"])
def test_process_failure_and_identity_mismatch_fail_gate(monkeypatch, tmp_path: Path, problem: str) -> None:
    args = arguments(tmp_path)

    def run(command, **kwargs):
        if problem == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        Path(command[-1]).write_text(json.dumps({"engine": "native", "status": "success", "input_sha256": "0" * 64}))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bench.subprocess, "run", run)
    report = bench.run_benchmark(args)
    assert not report["timing_samples_complete"]
    assert not report["engines"][0]["input_identity_verified"]


def test_model_identity_changes_with_weights(tmp_path: Path) -> None:
    (tmp_path / "model.bin").write_bytes(b"version1")
    before = bench.model_identity(tmp_path)
    (tmp_path / "model.bin").write_bytes(b"version2")
    assert bench.model_identity(tmp_path)["tree_sha256"] != before["tree_sha256"]
