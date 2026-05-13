from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing retrieval chunks file: {path}")
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _source_ids(chunk: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for ref in chunk.get("source_refs") or []:
        source_id = ref.get("source_id") if isinstance(ref, dict) else None
        if source_id:
            ids.add(str(source_id))
    return ids


def _coverage_for_expected_ids(retrieved: list[dict[str, Any]], expected_ids: set[str]) -> set[str]:
    covered: set[str] = set()
    for chunk in retrieved:
        covered.update(_source_ids(chunk) & expected_ids)
    return covered


def score_chunk(query: str, chunk: dict[str, Any]) -> float:
    """Return a deterministic local retrieval score for smoke/eval gates."""
    query_tokens = _tokens(query)
    chunk_tokens = _tokens(str(chunk.get("text") or ""))
    if not query_tokens or not chunk_tokens:
        return 0.0
    overlap = len(query_tokens & chunk_tokens)
    if overlap == 0:
        return 0.0
    priority = float(chunk.get("retrieval_priority") or 0) / 1000.0
    density = overlap / max(len(chunk_tokens), 1)
    return overlap + density + priority


def retrieve(query: str, chunks: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    scored = []
    for chunk in chunks:
        score = score_chunk(query, chunk)
        if score <= 0:
            continue
        scored.append((score, int(chunk.get("chunk_index") or 0), chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk | {"score": round(score, 6)} for score, _, chunk in scored[:top_k]]


def evaluate_queries(
    *,
    chunks: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    hit_count = 0
    reciprocal_rank_sum = 0.0
    expected_total = 0
    covered_total = 0
    requirement_expected_total = 0
    requirement_covered_total = 0
    table_field_expected_total = 0
    table_field_covered_total = 0

    for idx, case in enumerate(queries, start=1):
        query = str(case.get("query") or "").strip()
        expected_ids = {str(item) for item in case.get("expected_source_ids", [])}
        expected_requirement_ids = {str(item) for item in case.get("expected_requirement_source_ids", [])}
        expected_table_field_ids = {str(item) for item in case.get("expected_table_field_source_ids", [])}
        retrieved = retrieve(query, chunks, top_k=top_k)
        first_rank: int | None = None
        covered: set[str] = set()
        for rank, chunk in enumerate(retrieved, start=1):
            matched = _source_ids(chunk) & expected_ids
            if matched and first_rank is None:
                first_rank = rank
            covered.update(matched)

        hit = first_rank is not None if expected_ids else bool(retrieved)
        hit_count += int(hit)
        reciprocal_rank_sum += (1.0 / first_rank) if first_rank else 0.0
        expected_total += len(expected_ids)
        covered_total += len(covered)
        requirement_covered = _coverage_for_expected_ids(retrieved, expected_requirement_ids)
        table_field_covered = _coverage_for_expected_ids(retrieved, expected_table_field_ids)
        requirement_expected_total += len(expected_requirement_ids)
        requirement_covered_total += len(requirement_covered)
        table_field_expected_total += len(expected_table_field_ids)
        table_field_covered_total += len(table_field_covered)
        results.append(
            {
                "query_index": idx,
                "query": query,
                "expected_source_ids": sorted(expected_ids),
                "hit": hit,
                "first_hit_rank": first_rank,
                "covered_source_ids": sorted(covered),
                "expected_requirement_source_ids": sorted(expected_requirement_ids),
                "covered_requirement_source_ids": sorted(requirement_covered),
                "expected_table_field_source_ids": sorted(expected_table_field_ids),
                "covered_table_field_source_ids": sorted(table_field_covered),
                "retrieved": [
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "chunk_type": chunk.get("chunk_type"),
                        "score": chunk.get("score"),
                        "source_ids": sorted(_source_ids(chunk)),
                    }
                    for chunk in retrieved
                ],
            }
        )

    query_count = len(queries)
    token_lengths = [int(chunk.get("token_estimate") or 0) for chunk in chunks]
    token_lengths_sorted = sorted(token_lengths)
    p95_index = int(round((len(token_lengths_sorted) - 1) * 0.95)) if token_lengths_sorted else 0
    return {
        "schema_version": "1.0",
        "top_k": top_k,
        "query_count": query_count,
        "metrics": {
            "hit_at_k": round(hit_count / query_count, 4) if query_count else 0.0,
            "mrr": round(reciprocal_rank_sum / query_count, 4) if query_count else 0.0,
            "citation_coverage": round(covered_total / expected_total, 4) if expected_total else 0.0,
            "requirement_coverage": round(requirement_covered_total / requirement_expected_total, 4)
            if requirement_expected_total
            else 0.0,
            "table_field_coverage": round(table_field_covered_total / table_field_expected_total, 4)
            if table_field_expected_total
            else 0.0,
            "chunk_token_max": max(token_lengths, default=0),
            "chunk_token_p95": token_lengths_sorted[p95_index] if token_lengths_sorted else 0,
        },
        "results": results,
    }


def _load_eval_set(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    queries = payload.get("queries") if isinstance(payload, dict) else payload
    if not isinstance(queries, list):
        raise ValueError("Eval set must be a list or an object with a 'queries' list.")
    return [dict(item) for item in queries]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval chunks with deterministic local scoring.")
    parser.add_argument("--output-dir", type=Path, required=True, help="pdf2md output directory.")
    parser.add_argument("--eval-set", type=Path, required=True, help="JSON eval set with queries.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args(argv)

    chunks = _read_jsonl(args.output_dir / "retrieval_chunks_rag.jsonl")
    queries = _load_eval_set(args.eval_set)
    report = evaluate_queries(chunks=chunks, queries=queries, top_k=args.top_k)
    report_path = args.report_path or args.output_dir / "rag_eval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
