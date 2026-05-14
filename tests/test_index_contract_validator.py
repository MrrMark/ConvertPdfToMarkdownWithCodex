from __future__ import annotations

import json
from pathlib import Path

from pdf2md.models import IndexContractReport
from scripts.validate_index_contract import main, validate_index_contract


SOURCE_SHA256 = "a" * 64


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _valid_chunk(**overrides) -> dict:
    text = overrides.pop("text", "The controller shall return SUCCESS.")
    chunk = {
        "chunk_id": "chunk-000001",
        "schema_version": "1.0",
        "chunk_index": 1,
        "chunk_type": "requirement",
        "text": text,
        "source_sha256": SOURCE_SHA256,
        "source_refs": [
            {
                "source_type": "requirement_trace",
                "source_id": "req-trace-000001",
                "page": 1,
                "bbox": [72.0, 92.0, 240.0, 102.0],
            }
        ],
        "page_range": [1, 1],
        "bbox": [72.0, 92.0, 240.0, 102.0],
        "heading_path": ["1 Requirements"],
        "semantic_types": ["requirement"],
        "normative_strength": "required",
        "retrieval_priority": 100,
        "char_count": len(text),
        "token_estimate": 9,
        "section_path": "1 Requirements",
        "chunk_group_id": "requirement-page-0001",
        "source_record_count": 1,
        "source_dedupe_key": "req-trace-000001",
        "chunk_boundary_policy": "source_record",
        "chunk_boundary_reasons": ["requirement_boundary"],
    }
    chunk.update(overrides)
    return chunk


def test_index_contract_accepts_valid_retrieval_chunk_for_all_targets(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])

    report = validate_index_contract(output_dir=tmp_path, target="all")

    validated = IndexContractReport.model_validate(report)
    assert validated.status == "passed"
    assert validated.passed is True
    assert validated.summary.checked_files == 1
    assert validated.summary.checked_records == 1
    assert validated.findings == []
    assert validated.targets == ["openai", "azure-ai-search", "langchain", "llamaindex"]


def test_index_contract_reports_required_field_type_and_source_ref_errors(tmp_path: Path) -> None:
    broken = _valid_chunk(source_refs=[], page_range=[2, 1], retrieval_priority="high")
    broken.pop("schema_version")
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [broken])

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    codes = [finding["code"] for finding in report["findings"]]
    assert report["status"] == "failed"
    assert report["summary"]["error_count"] >= 4
    assert "missing_required_field" in codes
    assert "schema_version_mismatch" in codes
    assert "missing_source_refs" in codes
    assert "invalid_page_range" in codes
    assert "invalid_integer_field" in codes
    assert report["findings"][0]["severity"] == "error"
    assert report["findings"][0]["line"] == 1


def test_index_contract_reports_metadata_size_guardrail_as_warning(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])

    report = validate_index_contract(output_dir=tmp_path, target="openai", metadata_max_bytes=10)

    assert report["status"] == "warning"
    assert report["passed"] is True
    assert report["summary"]["error_count"] == 0
    assert "metadata_size_exceeds_limit" in {finding["code"] for finding in report["findings"]}


def test_index_contract_confidential_safe_detects_paths_filename_and_hash(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(
        tmp_path / "figures_rag.jsonl",
        [
            {
                "figure_id": "page-0001-figure-0001",
                "page": 1,
                "path": "/Users/example/specs/customer-diagram.png",
                "source_refs": [
                    {
                        "source_type": "figure",
                        "source_id": "page-0001-figure-0001",
                        "page": 1,
                        "path": "/Users/example/specs/customer-diagram.png",
                    }
                ],
            }
        ],
    )
    (tmp_path / "manifest.json").write_text(json.dumps({"input_file": "secret-spec.pdf"}), encoding="utf-8")

    report = validate_index_contract(output_dir=tmp_path, target="openai", confidential_safe=True)

    codes = {finding["code"] for finding in report["findings"]}
    assert report["status"] == "warning"
    assert "confidential_absolute_path" in codes
    assert "confidential_filename_exposed" in codes
    assert "confidential_source_hash_requires_review" in codes
    assert "text_redaction_not_performed" in codes


def test_index_contract_main_writes_report_and_honors_fail_on_error(tmp_path: Path) -> None:
    report_file = tmp_path / "contract.json"

    exit_code = main(
        [
            "--output-dir",
            str(tmp_path),
            "--target",
            "openai",
            "--report-file",
            str(report_file),
            "--fail-on-error",
        ]
    )

    assert exit_code == 1
    payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["findings"][0]["code"] == "missing_required_file"
