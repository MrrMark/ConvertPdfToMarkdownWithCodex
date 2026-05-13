from __future__ import annotations

import json
from pathlib import Path

from scripts.run_rag_eval import apply_calibration_gate, evaluate_queries, main


def _chunk(chunk_id: str, text: str, source_id: str, priority: int = 50) -> dict:
    return {
        "chunk_id": chunk_id,
        "chunk_index": int(chunk_id.rsplit("-", 1)[1]),
        "chunk_type": "text_block",
        "text": text,
        "source_refs": [{"source_type": "text_block", "source_id": source_id, "page": 1}],
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
        "requirement_coverage": 1.0,
        "table_field_coverage": 0.0,
        "chunk_token_max": 0,
        "chunk_token_p95": 0,
    }
    assert report["results"][0]["retrieved"][0]["chunk_id"] == "chunk-000001"


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
