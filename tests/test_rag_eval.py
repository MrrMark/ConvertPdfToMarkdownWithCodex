from __future__ import annotations

import json
from pathlib import Path

from scripts.run_rag_eval import apply_calibration_gate, evaluate_queries, main


def _chunk(chunk_id: str, text: str, source_id: str, priority: int = 50, source_type: str = "text_block") -> dict:
    return {
        "chunk_id": chunk_id,
        "chunk_index": int(chunk_id.rsplit("-", 1)[1]),
        "chunk_type": "text_block",
        "text": text,
        "source_refs": [{"source_type": source_type, "source_id": source_id, "page": 1}],
        "retrieval_priority": priority,
    }


def test_rag_eval_reports_hit_mrr_and_citation_coverage() -> None:
    chunks = [
        _chunk("chunk-000001", "The controller shall return SUCCESS.", "page-0001-block-0001", 100),
        _chunk("chunk-000002", "Unrelated namespace content.", "page-0001-block-0002"),
    ]

    report = evaluate_queries(
        chunks=chunks,
        queries=[
            {
                "query": "controller success",
                "expected_source_ids": ["page-0001-block-0001"],
                "expected_requirement_source_ids": ["page-0001-block-0001"],
            }
        ],
        top_k=1,
    )

    assert report["metrics"] == {
        "hit_at_k": 1.0,
        "mrr": 1.0,
        "citation_coverage": 1.0,
        "expected_source_coverage": 1.0,
        "expected_source_hit_count": 1,
        "expected_source_total_count": 1,
        "expected_source_miss_count": 0,
        "requirement_coverage": 1.0,
        "table_field_coverage": 0.0,
        "chunk_count": 2,
        "chunk_token_max": 0,
        "chunk_token_p95": 0,
        "chunk_size_compliance": 1.0,
        "source_ref_presence_coverage": 1.0,
        "duplicate_source_ratio": 0.0,
        "merged_chunk_count": 0,
        "merged_source_chunk_count": 0,
        "average_source_record_count": 1.0,
        "table_contextual_embedding_coverage": 0.0,
        "table_contextual_embedding_count": 0,
        "table_contextual_embedding_total": 0,
    }
    assert report["results"][0]["retrieved"][0]["chunk_id"] == "chunk-000001"


def test_rag_eval_matches_chunk_ids_and_filters_expected_source_types() -> None:
    chunks = [
        _chunk("chunk-000001", "Status field table row.", "page-0001-table-0001-row-0001", 80, "table_row"),
        _chunk("chunk-000002", "Status field text block.", "page-0001-block-0001", 80),
    ]

    report = evaluate_queries(
        chunks=chunks,
        queries=[
            {
                "query": "status field",
                "expected_source_ids": ["chunk-000001", "page-0001-table-0001-row-0001", "page-0001-block-0001"],
                "expected_source_types": ["chunk", "table_row"],
            }
        ],
        top_k=2,
    )

    result = report["results"][0]
    assert report["metrics"]["expected_source_coverage"] == 0.6667
    assert report["metrics"]["expected_source_hit_count"] == 1
    assert result["covered_source_ids"] == ["chunk-000001", "page-0001-table-0001-row-0001"]
    assert result["missing_expected_source_ids"] == ["page-0001-block-0001"]


def test_rag_eval_scores_optional_embedding_text_and_reports_intrinsic_metrics() -> None:
    chunks = [
        _chunk("chunk-000001", "Field = STS | Description = ok.", "page-0001-table-0001-row-0001", 80, "table_row")
        | {
            "chunk_type": "table_row",
            "embedding_text": "Caption: Table 1 Status Fields\nHeaders: Field | Description\nText: Field = STS",
            "token_estimate": 12,
            "source_dedupe_key": "page-0001-table-0001-row-0001",
        },
        _chunk("chunk-000002", "Unrelated body text.", "page-0001-block-0001")
        | {"token_estimate": 4, "source_dedupe_key": "page-0001-block-0001"},
    ]

    report = evaluate_queries(
        chunks=chunks,
        queries=[
            {
                "query": "status fields",
                "expected_source_ids": ["page-0001-table-0001-row-0001"],
                "expected_source_types": ["table_row"],
            }
        ],
        top_k=1,
    )

    assert report["results"][0]["retrieved"][0]["chunk_id"] == "chunk-000001"
    assert report["metrics"]["table_contextual_embedding_coverage"] == 1.0
    assert report["metrics"]["table_contextual_embedding_count"] == 1
    assert report["metrics"]["table_contextual_embedding_total"] == 1
    assert report["metrics"]["chunk_size_compliance"] == 1.0
    assert report["metrics"]["duplicate_source_ratio"] == 0.0


def test_rag_eval_reports_merged_text_chunk_metrics() -> None:
    chunks = [
        _chunk("chunk-000001", "Alpha status.\n\nBeta status.", "page-0001-block-0001")
        | {
            "chunk_boundary_policy": "merged_sibling_text_blocks",
            "chunk_boundary_reasons": ["sibling_text_merge", "text_block_boundary"],
            "merged_source_chunk_count": 2,
            "source_record_count": 2,
            "source_refs": [
                {"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1},
                {"source_type": "text_block", "source_id": "page-0001-block-0002", "page": 1},
            ],
            "token_estimate": 4,
        },
        _chunk("chunk-000002", "Gamma status.", "page-0001-block-0003") | {"token_estimate": 2},
    ]

    report = evaluate_queries(chunks=chunks, queries=[], top_k=1)

    assert report["metrics"]["chunk_count"] == 2
    assert report["metrics"]["merged_chunk_count"] == 1
    assert report["metrics"]["merged_source_chunk_count"] == 2
    assert report["metrics"]["average_source_record_count"] == 1.5


def test_rag_eval_cli_writes_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "retrieval_chunks_rag.jsonl").write_text(
        json.dumps(_chunk("chunk-000001", "Field Status describes current status.", "page-0001-table-0001-row-0001"))
        + "\n",
        encoding="utf-8",
    )
    eval_set = tmp_path / "eval.json"
    eval_set.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query": "current status field",
                        "expected_source_ids": ["page-0001-table-0001-row-0001"],
                        "expected_table_field_source_ids": ["page-0001-table-0001-row-0001"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["--output-dir", str(output_dir), "--eval-set", str(eval_set), "--top-k", "3"]) == 0
    report = json.loads((output_dir / "rag_eval_report.json").read_text(encoding="utf-8"))
    assert report["metrics"]["hit_at_k"] == 1.0
    assert report["metrics"]["expected_source_coverage"] == 1.0
    assert report["metrics"]["table_field_coverage"] == 1.0


def test_rag_eval_calibration_gate_uses_thresholds_and_output_diagnostics(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "retrieval_chunks_rag.jsonl").write_text(
        json.dumps(
            _chunk(
                "chunk-000001",
                "REQ-1 shall return GOOD when enabled.",
                "req-trace-000001",
                priority=100,
            )
            | {"token_estimate": 8}
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "cross_refs_rag.jsonl").write_text(
        json.dumps({"ref_id": "ref-1", "resolved": True})
        + "\n"
        + json.dumps({"ref_id": "ref-2", "resolved": False})
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.json").write_text(json.dumps({"duration_ms": 1234}), encoding="utf-8")
    eval_set = tmp_path / "eval.json"
    eval_set.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query": "return good",
                        "expected_source_ids": ["req-trace-000001"],
                        "expected_requirement_source_ids": ["req-trace-000001"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--output-dir",
            str(output_dir),
            "--eval-set",
            str(eval_set),
            "--min-hit-at-k",
            "1.0",
            "--min-expected-source-coverage",
            "1.0",
            "--min-cross-ref-resolved-coverage",
            "0.75",
            "--max-conversion-duration-ms",
            "1000",
            "--fail-on-threshold",
        ]
    )

    report = json.loads((output_dir / "rag_eval_report.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["metrics"]["cross_ref_resolved_coverage"] == 0.5
    assert report["metrics"]["conversion_duration_ms"] == 1234
    assert report["passed_calibration_gate"] is False
    assert {failure["metric"] for failure in report["gate_failures"]} == {
        "cross_ref_resolved_coverage",
        "conversion_duration_ms",
    }


def test_rag_eval_calibration_gate_fails_expected_source_coverage() -> None:
    result = apply_calibration_gate(
        {"metrics": {"expected_source_coverage": 0.5}},
        thresholds={"min_expected_source_coverage": 0.75},
    )

    assert result["passed_calibration_gate"] is False
    assert result["gate_failures"] == [
        {
            "type": "threshold_failure",
            "metric": "expected_source_coverage",
            "limit": 0.75,
            "current": 0.5,
            "direction": "min",
        }
    ]


def test_rag_eval_calibration_gate_can_pass_without_threshold_failures() -> None:
    report = {"metrics": {"hit_at_k": 1.0, "chunk_token_p95": 400}}

    result = apply_calibration_gate(
        report,
        calibration_profile="synthetic",
        thresholds={"min_hit_at_k": 1.0, "max_chunk_token_p95": 512},
    )

    assert result["calibration_profile"] == "synthetic"
    assert result["passed_calibration_gate"] is True
    assert result["gate_failures"] == []


def test_rag_eval_cli_accepts_calibration_profile(tmp_path: Path) -> None:
    output_dir = tmp_path / "output-profile"
    output_dir.mkdir()
    (output_dir / "retrieval_chunks_rag.jsonl").write_text(
        json.dumps(_chunk("chunk-000001", "The controller shall return SUCCESS.", "req-trace-000001"))
        + "\n",
        encoding="utf-8",
    )
    eval_set = tmp_path / "eval-profile.json"
    eval_set.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query": "controller success",
                        "expected_source_ids": ["req-trace-000001"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps({"profile_name": "local-profile", "thresholds": {"min_hit_at_k": 1.0}}),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--output-dir",
                str(output_dir),
                "--eval-set",
                str(eval_set),
                "--calibration-profile",
                str(profile),
                "--fail-on-threshold",
            ]
        )
        == 0
    )
    report = json.loads((output_dir / "rag_eval_report.json").read_text(encoding="utf-8"))
    assert report["calibration_profile"] == "local-profile"
    assert report["passed_calibration_gate"] is True
