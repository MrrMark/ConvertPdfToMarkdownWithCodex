from __future__ import annotations

import json
from pathlib import Path

from pdf2md.models import ProvenanceIntegrityReport
from scripts.validate_provenance_integrity import main, validate_provenance_integrity


SOURCE_SHA256 = "b" * 64


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _write_valid_sidecars(output_dir: Path) -> None:
    _write_jsonl(
        output_dir / "text_blocks_rag.jsonl",
        [
            {
                "block_id": "page-0001-block-0001",
                "page": 1,
                "block_index": 1,
                "block_type": "paragraph",
                "text": "The controller shall return SUCCESS.",
                "bbox": [72.0, 92.0, 240.0, 102.0],
                "heading_path": ["1 Requirements"],
            }
        ],
    )
    _write_jsonl(
        output_dir / "semantic_units_rag.jsonl",
        [
            {
                "semantic_id": "page-0001-sem-0001",
                "semantic_index": 1,
                "semantic_type": "requirement",
                "text": "The controller shall return SUCCESS.",
                "source_refs": [
                    {
                        "source_type": "text_block",
                        "source_id": "page-0001-block-0001",
                        "page": 1,
                        "bbox": [72.0, 92.0, 240.0, 102.0],
                    }
                ],
                "page_range": [1, 1],
                "bbox": [72.0, 92.0, 240.0, 102.0],
                "heading_path": ["1 Requirements"],
            }
        ],
    )
    _write_jsonl(
        output_dir / "requirements_rag.jsonl",
        [
            {
                "semantic_id": "page-0001-sem-0001",
                "semantic_index": 1,
                "semantic_type": "requirement",
                "text": "The controller shall return SUCCESS.",
                "source_refs": [
                    {
                        "source_type": "text_block",
                        "source_id": "page-0001-block-0001",
                        "page": 1,
                        "bbox": [72.0, 92.0, 240.0, 102.0],
                    }
                ],
                "page_range": [1, 1],
                "bbox": [72.0, 92.0, 240.0, 102.0],
                "heading_path": ["1 Requirements"],
            }
        ],
    )
    _write_jsonl(
        output_dir / "requirement_traceability_rag.jsonl",
        [
            {
                "trace_id": "req-trace-000001",
                "trace_index": 1,
                "text": "The controller shall return SUCCESS.",
                "source_refs": [
                    {
                        "source_type": "text_block",
                        "source_id": "page-0001-block-0001",
                        "page": 1,
                        "bbox": [72.0, 92.0, 240.0, 102.0],
                    }
                ],
                "page_range": [1, 1],
                "bbox": [72.0, 92.0, 240.0, 102.0],
            }
        ],
    )
    _write_jsonl(
        output_dir / "retrieval_chunks_rag.jsonl",
        [
            {
                "chunk_id": "chunk-000001",
                "schema_version": "1.0",
                "chunk_index": 1,
                "chunk_type": "requirement",
                "text": "The controller shall return SUCCESS.",
                "source_sha256": SOURCE_SHA256,
                "source_refs": [
                    {
                        "source_type": "text_block",
                        "source_id": "page-0001-block-0001",
                        "page": 1,
                        "bbox": [72.0, 92.0, 240.0, 102.0],
                    },
                    {
                        "source_type": "requirement",
                        "source_id": "page-0001-sem-0001",
                        "page": 1,
                        "bbox": [72.0, 92.0, 240.0, 102.0],
                    },
                ],
                "page_range": [1, 1],
                "bbox": [72.0, 92.0, 240.0, 102.0],
                "heading_path": ["1 Requirements"],
                "semantic_types": ["requirement"],
                "normative_strength": "required",
                "retrieval_priority": 100,
                "char_count": 36,
                "token_estimate": 9,
                "section_path": "1 Requirements",
                "chunk_group_id": "requirement-page-0001",
                "source_record_count": 2,
                "source_dedupe_key": "page-0001-block-0001|page-0001-sem-0001",
                "chunk_boundary_policy": "source_record",
                "chunk_boundary_reasons": ["requirement_boundary"],
            }
        ],
    )
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "summary": {
                    "rag_text_block_record_count": 1,
                    "semantic_unit_record_count": 1,
                    "requirement_record_count": 1,
                    "requirement_traceability_record_count": 1,
                    "retrieval_chunk_record_count": 1,
                }
            }
        ),
        encoding="utf-8",
    )


def test_provenance_integrity_accepts_resolved_sidecars(tmp_path: Path) -> None:
    _write_valid_sidecars(tmp_path)

    report = validate_provenance_integrity(output_dir=tmp_path)

    validated = ProvenanceIntegrityReport.model_validate(report)
    assert validated.status == "passed"
    assert validated.passed is True
    assert validated.summary.checked_source_refs == 5
    assert validated.summary.resolved_source_refs == 5
    assert validated.summary.unresolved_source_refs == 0
    assert validated.findings == []


def test_provenance_integrity_accepts_excluded_figure_self_refs(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "figures_rag.jsonl",
        [
            {
                "figure_id": "page-0001-figure-0001",
                "page": 1,
                "record_type": "excluded_image",
                "status": "excluded",
                "bbox": [72.0, 92.0, 92.0, 100.0],
                "source_refs": [
                    {
                        "source_type": "excluded_figure",
                        "source_id": "page-0001-figure-0001",
                        "page": 1,
                        "bbox": [72.0, 92.0, 92.0, 100.0],
                    }
                ],
            }
        ],
    )
    (tmp_path / "report.json").write_text(
        json.dumps({"summary": {"figure_rag_record_count": 1}}),
        encoding="utf-8",
    )

    report = validate_provenance_integrity(output_dir=tmp_path)

    assert report["status"] == "passed"
    assert report["summary"]["checked_source_refs"] == 1
    assert report["summary"]["resolved_source_refs"] == 1
    assert report["findings"] == []


def test_provenance_integrity_reports_unresolved_page_and_dedupe_mismatches(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "text_blocks_rag.jsonl",
        [
            {
                "block_id": "page-0001-block-0001",
                "page": 1,
                "text": "Source text",
                "bbox": [72.0, 92.0, 240.0, 102.0],
            }
        ],
    )
    _write_jsonl(
        tmp_path / "retrieval_chunks_rag.jsonl",
        [
            {
                "chunk_id": "chunk-000001",
                "source_refs": [
                    {"source_type": "text_block", "source_id": "missing-block", "page": 2},
                    {"source_type": "unknown_source", "source_id": "mystery", "page": 1},
                ],
                "page_range": [1, 1],
                "source_record_count": 3,
                "source_dedupe_key": "not-derived",
            }
        ],
    )
    (tmp_path / "report.json").write_text(
        json.dumps({"summary": {"retrieval_chunk_record_count": 99}}),
        encoding="utf-8",
    )

    report = validate_provenance_integrity(output_dir=tmp_path)

    codes = [finding["code"] for finding in report["findings"]]
    assert report["status"] == "failed"
    assert "unresolved_source_ref" in codes
    assert "source_ref_outside_record_page_range" in codes
    assert "source_record_count_mismatch" in codes
    assert "source_dedupe_key_mismatch" in codes
    assert "unknown_source_type" in codes
    assert "report_record_count_mismatch" in codes
    assert report["findings"][0]["severity"] == "error"
    assert report["findings"][0]["line"] == 1


def test_provenance_integrity_main_writes_report_and_honors_fail_on_error(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "retrieval_chunks_rag.jsonl",
        [{"chunk_id": "chunk-000001", "source_refs": [{"source_type": "text_block", "source_id": "missing", "page": 1}]}],
    )
    report_file = tmp_path / "provenance.json"

    exit_code = main(
        [
            "--output-dir",
            str(tmp_path),
            "--report-file",
            str(report_file),
            "--fail-on-error",
        ]
    )

    assert exit_code == 1
    payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["findings"][0]["code"] == "unresolved_source_ref"
