from __future__ import annotations

import json
from pathlib import Path

from scripts.run_rag_eval import evaluate_queries, main


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
        queries=[{"query": "controller success", "expected_source_ids": ["page-0001-block-0001"]}],
        top_k=1,
    )

    assert report["metrics"] == {"hit_at_k": 1.0, "mrr": 1.0, "citation_coverage": 1.0}
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
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["--output-dir", str(output_dir), "--eval-set", str(eval_set), "--top-k", "3"]) == 0
    report = json.loads((output_dir / "rag_eval_report.json").read_text(encoding="utf-8"))
    assert report["metrics"]["hit_at_k"] == 1.0
