from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts.run_rag_eval import evaluate_queries
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from run_rag_eval import evaluate_queries  # type: ignore[no-redef]


VISUAL_CHUNK_TYPES = ("figure_text", "figure_description", "figure_structure")
FIGURE_SOURCE_TYPES = {"figure", "excluded_figure"}
VISUAL_SOURCE_TYPES_BY_CHUNK_TYPE = {
    "figure_text": FIGURE_SOURCE_TYPES,
    "figure_description": FIGURE_SOURCE_TYPES | {"figure_description"},
    "figure_structure": FIGURE_SOURCE_TYPES | {"figure_structure"},
}
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _source_ids(chunk: dict[str, Any], *, source_types: set[str]) -> list[str]:
    ids: list[str] = []
    for ref in chunk.get("source_refs") or []:
        if not isinstance(ref, dict):
            continue
        source_type = str(ref.get("source_type") or "")
        source_id = str(ref.get("source_id") or "")
        if source_type in source_types and source_id:
            ids.append(source_id)
    return sorted(dict.fromkeys(ids))


def _query_text(chunk: dict[str, Any]) -> str:
    text = str(chunk.get("embedding_text") or chunk.get("text") or "")
    tokens = TOKEN_PATTERN.findall(text)
    if tokens:
        return " ".join(tokens[:12])
    return str(chunk.get("chunk_type") or "figure")


def _query_for_chunk(chunk: dict[str, Any]) -> dict[str, Any] | None:
    chunk_type = str(chunk.get("chunk_type") or "")
    source_types = VISUAL_SOURCE_TYPES_BY_CHUNK_TYPE.get(chunk_type)
    if source_types is None:
        return None
    expected_ids = _source_ids(chunk, source_types=source_types)
    if not expected_ids:
        return None
    return {
        "query": _query_text(chunk),
        "expected_source_ids": expected_ids,
        "expected_source_types": sorted(source_types),
    }


def _visual_queries(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for chunk_type in VISUAL_CHUNK_TYPES:
        for chunk in chunks:
            if chunk.get("chunk_type") != chunk_type:
                continue
            query = _query_for_chunk(chunk)
            if query is not None:
                queries.append(query)
                break
    return queries


def _figure_source_ref_coverage(chunks: list[dict[str, Any]]) -> float:
    visual_chunks = [chunk for chunk in chunks if chunk.get("chunk_type") in VISUAL_CHUNK_TYPES]
    if not visual_chunks:
        return 0.0
    covered = sum(1 for chunk in visual_chunks if _source_ids(chunk, source_types=FIGURE_SOURCE_TYPES))
    return round(covered / len(visual_chunks), 4)


def evaluate_visual_chunks(*, output_dir: Path, profile: str, top_k: int = 5) -> dict[str, Any]:
    """Evaluate visual retrieval chunks without storing raw query or retrieved text."""
    chunks = _read_jsonl(output_dir / "retrieval_chunks_rag.jsonl")
    visual_chunks = [chunk for chunk in chunks if chunk.get("chunk_type") in VISUAL_CHUNK_TYPES]
    queries = _visual_queries(visual_chunks)
    figure_source_ref_coverage = _figure_source_ref_coverage(visual_chunks)
    if not queries:
        return {
            "status": "skipped",
            "passed": True,
            "profile": profile,
            "top_k": top_k,
            "query_count": 0,
            "visual_chunk_count": len(visual_chunks),
            "metrics": {
                "hit_at_k": 0.0,
                "expected_source_coverage": 0.0,
                "figure_source_ref_coverage": figure_source_ref_coverage,
            },
            "queries_included": False,
            "retrieved_text_included": False,
            "raw_content_included": False,
        }
    report = evaluate_queries(chunks=chunks, queries=queries, top_k=top_k)
    metrics = report.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    selected_metrics = {
        "hit_at_k": float(metrics.get("hit_at_k") or 0.0),
        "expected_source_coverage": float(metrics.get("expected_source_coverage") or 0.0),
        "figure_source_ref_coverage": figure_source_ref_coverage,
    }
    passed = (
        selected_metrics["hit_at_k"] >= 1.0
        and selected_metrics["expected_source_coverage"] >= 1.0
        and selected_metrics["figure_source_ref_coverage"] >= 1.0
    )
    return {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "profile": profile,
        "top_k": top_k,
        "query_count": len(queries),
        "visual_chunk_count": len(visual_chunks),
        "metrics": selected_metrics,
        "queries_included": False,
        "retrieved_text_included": False,
        "raw_content_included": False,
    }
