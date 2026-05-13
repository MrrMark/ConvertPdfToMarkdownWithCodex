from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from pdf2md.config import Config
from pdf2md.models import CorpusManifest, Manifest, Report
from pdf2md.pipeline import run_conversion
from helpers.normalize_outputs import normalize_manifest, normalize_report
from scripts import export_output_schema


def test_generated_manifest_and_report_match_current_models(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "schema-contract"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", keep_page_markers=True))

    assert result.exit_code == 0
    manifest_payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report_payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

    manifest = Manifest.model_validate(manifest_payload)
    report = Report.model_validate(report_payload)

    assert manifest.schema_version == "1.0"
    assert report.schema_version == "1.0"
    assert report.summary.text_line_extract_count >= 1


def test_additive_optional_fields_do_not_change_normalized_contract(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "schema-additive"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", keep_page_markers=True))
    assert result.exit_code == 0

    manifest_payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report_payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest_with_extra = deepcopy(manifest_payload)
    report_with_extra = deepcopy(report_payload)
    manifest_with_extra["future_optional_field"] = {"ignored": True}
    report_with_extra["future_optional_field"] = {"ignored": True}
    report_with_extra["summary"]["future_optional_metric"] = 1

    Manifest.model_validate(manifest_with_extra)
    Report.model_validate(report_with_extra)

    assert normalize_manifest(manifest_payload) == normalize_manifest(manifest_with_extra)
    assert normalize_report(report_payload) == normalize_report(report_with_extra)


def test_output_schema_export_is_deterministic(tmp_path: Path) -> None:
    output_dir = tmp_path / "schema"

    written = export_output_schema.write_schema_files(output_dir)

    assert [path.name for path in written] == [
        "manifest.schema.json",
        "report.schema.json",
        "batch_report.schema.json",
        "corpus_manifest.schema.json",
        "corpus_diff_report.schema.json",
    ]
    assert export_output_schema.check_schema_files(output_dir) == []
    manifest_schema = json.loads((output_dir / "manifest.schema.json").read_text(encoding="utf-8"))
    corpus_schema = json.loads((output_dir / "corpus_manifest.schema.json").read_text(encoding="utf-8"))
    assert manifest_schema["properties"]["schema_version"]["default"] == "1.0"
    assert corpus_schema["properties"]["purpose"]["default"] == "rag_corpus_ingest"
    diff_schema = json.loads((output_dir / "corpus_diff_report.schema.json").read_text(encoding="utf-8"))
    assert diff_schema["properties"]["purpose"]["default"] == "rag_corpus_incremental_diff"


def test_corpus_manifest_model_accepts_rag_file_map() -> None:
    corpus = CorpusManifest.model_validate(
        {
            "schema_version": "1.0",
            "purpose": "rag_corpus_ingest",
            "input_dir": "/tmp/input",
            "output_dir": "/tmp/input/output",
            "documents": [
                {
                    "doc_id": "spec",
                    "input_pdf": "/tmp/input/spec.pdf",
                    "source_sha256": "0" * 64,
                    "output_dir": "/tmp/input/output/spec",
                    "status": "success",
                    "selected_pages": [1, 2],
                    "skipped": False,
                    "files": {
                        "markdown": "/tmp/input/output/spec/spec.md",
                        "manifest": "/tmp/input/output/spec/spec_manifest.json",
                        "report": "/tmp/input/output/spec/spec_report.json",
                        "retrieval_chunks_rag": "/tmp/input/output/spec/retrieval_chunks_rag.jsonl",
                        "requirement_traceability_rag": "/tmp/input/output/spec/requirement_traceability_rag.jsonl",
                        "technical_tables_rag": "/tmp/input/output/spec/technical_tables_rag.jsonl",
                    },
                }
            ],
        }
    )

    assert corpus.documents[0].files.retrieval_chunks_rag.endswith("retrieval_chunks_rag.jsonl")
    assert corpus.documents[0].files.technical_tables_rag.endswith("technical_tables_rag.jsonl")


def test_committed_output_schemas_match_current_models() -> None:
    schema_dir = Path("docs/schema")

    assert export_output_schema.check_schema_files(schema_dir) == []
