from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
TABLE_CONTEXT_CHUNK_TYPES = {"table_row", "technical_table", "domain_unit"}
DEFAULT_CHUNK_TOKEN_TARGET = 512
TEXT_CHUNK_MERGE_POLICY = "merged_sibling_text_blocks"
TEXT_CHUNK_MERGE_REASON = "sibling_text_merge"
DEFAULT_REQUIREMENT_SOURCE_TYPES = {"requirement", "requirement_trace"}
DEFAULT_TABLE_FIELD_SOURCE_TYPES = {"table_row", "technical_table_unit", "domain_unit"}
RELATIONSHIP_ID_FIELDS = (
    "previous_chunk_id",
    "next_chunk_id",
    "section_anchor_chunk_id",
)


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)}


def _retrieval_text(chunk: dict[str, Any]) -> str:
    embedding_text = chunk.get("embedding_text")
    if isinstance(embedding_text, str) and embedding_text.strip():
        return embedding_text
    return str(chunk.get("text") or "")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing retrieval chunks file: {path}")
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return _read_jsonl(path)


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _source_ids(
    chunk: dict[str, Any],
    *,
    source_types: set[str] | None = None,
    include_chunk_id: bool = True,
) -> set[str]:
    ids: set[str] = set()
    normalized_types = {item.casefold() for item in source_types or set() if item}
    if include_chunk_id:
        chunk_id = chunk.get("chunk_id")
        if chunk_id and (not normalized_types or normalized_types & {"chunk", "retrieval_chunk"}):
            ids.add(str(chunk_id))
    for ref in chunk.get("source_refs") or []:
        if not isinstance(ref, dict):
            continue
        source_type = str(ref.get("source_type") or "").casefold()
        if normalized_types and source_type not in normalized_types:
            continue
        source_id = ref.get("source_id")
        if source_id:
            ids.add(str(source_id))
    return ids


def _coverage_for_expected_ids(
    retrieved: list[dict[str, Any]],
    expected_ids: set[str],
    *,
    source_types: set[str] | None = None,
    include_chunk_id: bool = True,
) -> set[str]:
    covered: set[str] = set()
    for chunk in retrieved:
        covered.update(_source_ids(chunk, source_types=source_types, include_chunk_id=include_chunk_id) & expected_ids)
    return covered


def _relationship_targets(chunk: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for field in RELATIONSHIP_ID_FIELDS:
        value = chunk.get(field)
        if isinstance(value, str) and value:
            targets.append(value)
    related = chunk.get("related_chunk_ids")
    if isinstance(related, list):
        targets.extend(str(item) for item in related if isinstance(item, str) and item)
    return targets


def score_chunk(query: str, chunk: dict[str, Any]) -> float:
    """Return a deterministic local retrieval score for smoke/eval gates."""
    query_tokens = _tokens(query)
    chunk_tokens = _tokens(_retrieval_text(chunk))
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


def intrinsic_chunk_metrics(
    chunks: list[dict[str, Any]],
    *,
    target_tokens: int = DEFAULT_CHUNK_TOKEN_TARGET,
) -> dict[str, Any]:
    """Return local-only intrinsic quality metrics for retrieval chunk outputs."""
    token_lengths = [int(chunk.get("token_estimate") or 0) for chunk in chunks]
    token_lengths_sorted = sorted(token_lengths)
    p95_index = int(round((len(token_lengths_sorted) - 1) * 0.95)) if token_lengths_sorted else 0
    keyed_source_refs = [
        str(chunk.get("source_dedupe_key") or "")
        for chunk in chunks
        if chunk.get("source_dedupe_key")
    ]
    duplicate_source_count = len(keyed_source_refs) - len(set(keyed_source_refs))
    table_chunks = [
        chunk for chunk in chunks if str(chunk.get("chunk_type") or "") in TABLE_CONTEXT_CHUNK_TYPES
    ]
    contextual_table_chunks = [
        chunk
        for chunk in table_chunks
        if isinstance(chunk.get("embedding_text"), str)
        and chunk.get("embedding_text")
        and chunk.get("embedding_text") != chunk.get("text")
    ]
    source_ref_chunks = [chunk for chunk in chunks if isinstance(chunk.get("source_refs"), list) and chunk["source_refs"]]
    merged_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("chunk_boundary_policy") == TEXT_CHUNK_MERGE_POLICY
        or TEXT_CHUNK_MERGE_REASON in list(chunk.get("chunk_boundary_reasons") or [])
    ]
    source_record_counts = [
        int(chunk.get("source_record_count") or len(chunk.get("source_refs") or []))
        for chunk in chunks
    ]
    chunk_ids = {str(chunk.get("chunk_id")) for chunk in chunks if chunk.get("chunk_id")}
    relationship_target_count = 0
    relationship_target_missing_count = 0
    for chunk in chunks:
        for target in _relationship_targets(chunk):
            relationship_target_count += 1
            if target not in chunk_ids:
                relationship_target_missing_count += 1
    relationship_resolved_count = relationship_target_count - relationship_target_missing_count
    return {
        "chunk_count": len(chunks),
        "chunk_token_max": max(token_lengths, default=0),
        "chunk_token_p95": token_lengths_sorted[p95_index] if token_lengths_sorted else 0,
        "chunk_size_compliance": round(
            sum(1 for value in token_lengths if value <= target_tokens) / len(token_lengths),
            4,
        )
        if token_lengths
        else 0.0,
        "source_ref_presence_coverage": round(len(source_ref_chunks) / len(chunks), 4) if chunks else 0.0,
        "duplicate_source_ratio": round(duplicate_source_count / len(keyed_source_refs), 4)
        if keyed_source_refs
        else 0.0,
        "merged_chunk_count": len(merged_chunks),
        "merged_source_chunk_count": sum(int(chunk.get("merged_source_chunk_count") or 0) for chunk in merged_chunks),
        "average_source_record_count": round(sum(source_record_counts) / len(source_record_counts), 4)
        if source_record_counts
        else 0.0,
        "table_contextual_embedding_coverage": round(len(contextual_table_chunks) / len(table_chunks), 4)
        if table_chunks
        else 0.0,
        "table_contextual_embedding_count": len(contextual_table_chunks),
        "table_contextual_embedding_total": len(table_chunks),
        "relationship_target_coverage": round(relationship_resolved_count / relationship_target_count, 4)
        if relationship_target_count
        else 1.0,
        "relationship_target_count": relationship_target_count,
        "relationship_target_missing_count": relationship_target_missing_count,
    }


def evaluate_queries(
    *,
    chunks: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    top_k: int,
    chunk_token_target: int = DEFAULT_CHUNK_TOKEN_TARGET,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    hit_count = 0
    reciprocal_rank_sum = 0.0
    expected_total = 0
    covered_total = 0
    expected_source_hit_count = 0
    requirement_expected_total = 0
    requirement_covered_total = 0
    table_field_expected_total = 0
    table_field_covered_total = 0

    for idx, case in enumerate(queries, start=1):
        query = str(case.get("query") or "").strip()
        expected_ids = {str(item) for item in case.get("expected_source_ids", [])}
        expected_source_types = {str(item) for item in case.get("expected_source_types", [])}
        expected_requirement_ids = {str(item) for item in case.get("expected_requirement_source_ids", [])}
        expected_table_field_ids = {str(item) for item in case.get("expected_table_field_source_ids", [])}
        expected_requirement_types = {
            str(item) for item in case.get("expected_requirement_source_types", DEFAULT_REQUIREMENT_SOURCE_TYPES)
        }
        expected_table_field_types = {
            str(item) for item in case.get("expected_table_field_source_types", DEFAULT_TABLE_FIELD_SOURCE_TYPES)
        }
        retrieved = retrieve(query, chunks, top_k=top_k)
        first_rank: int | None = None
        covered: set[str] = set()
        for rank, chunk in enumerate(retrieved, start=1):
            matched = _source_ids(chunk, source_types=expected_source_types) & expected_ids
            if matched and first_rank is None:
                first_rank = rank
            covered.update(matched)

        hit = first_rank is not None if expected_ids else bool(retrieved)
        hit_count += int(hit)
        expected_source_hit_count += int(bool(covered)) if expected_ids else 0
        reciprocal_rank_sum += (1.0 / first_rank) if first_rank else 0.0
        expected_total += len(expected_ids)
        covered_total += len(covered)
        requirement_covered = _coverage_for_expected_ids(
            retrieved,
            expected_requirement_ids,
            source_types=expected_requirement_types,
            include_chunk_id=False,
        )
        table_field_covered = _coverage_for_expected_ids(
            retrieved,
            expected_table_field_ids,
            source_types=expected_table_field_types,
            include_chunk_id=False,
        )
        requirement_expected_total += len(expected_requirement_ids)
        requirement_covered_total += len(requirement_covered)
        table_field_expected_total += len(expected_table_field_ids)
        table_field_covered_total += len(table_field_covered)
        results.append(
            {
                "query_index": idx,
                "query": query,
                "expected_source_ids": sorted(expected_ids),
                "expected_source_types": sorted(expected_source_types),
                "hit": hit,
                "first_hit_rank": first_rank,
                "covered_source_ids": sorted(covered),
                "missing_expected_source_ids": sorted(expected_ids - covered),
                "expected_requirement_source_ids": sorted(expected_requirement_ids),
                "expected_requirement_source_types": sorted(expected_requirement_types)
                if expected_requirement_ids
                else [],
                "covered_requirement_source_ids": sorted(requirement_covered),
                "expected_table_field_source_ids": sorted(expected_table_field_ids),
                "expected_table_field_source_types": sorted(expected_table_field_types)
                if expected_table_field_ids
                else [],
                "covered_table_field_source_ids": sorted(table_field_covered),
                "retrieved": [
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "chunk_type": chunk.get("chunk_type"),
                        "score": chunk.get("score"),
                        "source_ids": sorted(_source_ids(chunk)),
                        "source_types": sorted(
                            {
                                str(ref.get("source_type"))
                                for ref in chunk.get("source_refs") or []
                                if isinstance(ref, dict) and ref.get("source_type")
                            }
                        ),
                    }
                    for chunk in retrieved
                ],
            }
        )

    query_count = len(queries)
    intrinsic_metrics = intrinsic_chunk_metrics(chunks, target_tokens=chunk_token_target)
    return {
        "schema_version": "1.0",
        "top_k": top_k,
        "query_count": query_count,
        "metrics": {
            "hit_at_k": round(hit_count / query_count, 4) if query_count else 0.0,
            "mrr": round(reciprocal_rank_sum / query_count, 4) if query_count else 0.0,
            "citation_coverage": round(covered_total / expected_total, 4) if expected_total else 0.0,
            "expected_source_coverage": round(covered_total / expected_total, 4) if expected_total else 0.0,
            "expected_source_hit_count": expected_source_hit_count,
            "expected_source_total_count": expected_total,
            "expected_source_miss_count": max(expected_total - covered_total, 0),
            "requirement_coverage": round(requirement_covered_total / requirement_expected_total, 4)
            if requirement_expected_total
            else 0.0,
            "table_field_coverage": round(table_field_covered_total / table_field_expected_total, 4)
            if table_field_expected_total
            else 0.0,
            **intrinsic_metrics,
        },
        "results": results,
    }


def _load_eval_set(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    queries = payload.get("queries") if isinstance(payload, dict) else payload
    if not isinstance(queries, list):
        raise ValueError("Eval set must be a list or an object with a 'queries' list.")
    return [dict(item) for item in queries]


def collect_output_diagnostics(output_dir: Path) -> dict[str, Any]:
    """Collect deterministic RAG operation diagnostics from a conversion output."""
    cross_refs = _read_optional_jsonl(output_dir / "cross_refs_rag.jsonl")
    resolved_cross_refs = sum(1 for record in cross_refs if bool(record.get("resolved")))
    report = _read_optional_json(output_dir / "report.json")
    duration_ms = report.get("duration_ms") if isinstance(report, dict) else None
    cross_ref_total = len(cross_refs)
    return {
        "cross_ref_total": cross_ref_total,
        "cross_ref_resolved_count": resolved_cross_refs,
        "cross_ref_resolved_coverage": round(resolved_cross_refs / cross_ref_total, 4)
        if cross_ref_total
        else 0.0,
        "conversion_duration_ms": duration_ms if isinstance(duration_ms, int) else None,
    }


def _threshold_failure(
    *,
    metric: str,
    current: Any,
    limit: float,
    direction: str,
) -> dict[str, Any] | None:
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return {
            "type": "threshold_unavailable",
            "metric": metric,
            "limit": limit,
            "current": current,
            "direction": direction,
        }
    failed = current < limit if direction == "min" else current > limit
    if not failed:
        return None
    return {
        "type": "threshold_failure",
        "metric": metric,
        "limit": limit,
        "current": current,
        "direction": direction,
    }


def _profile_thresholds(path: Path | None) -> tuple[str | None, dict[str, float]]:
    if path is None:
        return None, {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile_name = None
    if isinstance(payload, dict):
        profile_name = payload.get("profile_name") or payload.get("name")
    thresholds = payload.get("thresholds") if isinstance(payload, dict) else None
    if not isinstance(thresholds, dict):
        raise ValueError("Calibration profile must contain a 'thresholds' object.")
    return str(profile_name) if profile_name else path.stem, {
        str(key): float(value) for key, value in thresholds.items() if isinstance(value, (int, float))
    }


def apply_calibration_gate(
    report: dict[str, Any],
    *,
    calibration_profile: str | None = None,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    """Apply local RAG calibration thresholds without external service calls."""
    metrics = report.setdefault("metrics", {})
    failures: list[dict[str, Any]] = []
    min_metrics = {
        "hit_at_k": "min_hit_at_k",
        "mrr": "min_mrr",
        "citation_coverage": "min_citation_coverage",
        "expected_source_coverage": "min_expected_source_coverage",
        "requirement_coverage": "min_requirement_coverage",
        "table_field_coverage": "min_table_field_coverage",
        "cross_ref_resolved_coverage": "min_cross_ref_resolved_coverage",
        "chunk_size_compliance": "min_chunk_size_compliance",
        "source_ref_presence_coverage": "min_source_ref_presence_coverage",
        "table_contextual_embedding_coverage": "min_table_contextual_embedding_coverage",
        "relationship_target_coverage": "min_relationship_target_coverage",
    }
    max_metrics = {
        "chunk_token_p95": "max_chunk_token_p95",
        "chunk_token_max": "max_chunk_token_max",
        "duplicate_source_ratio": "max_duplicate_source_ratio",
        "conversion_duration_ms": "max_conversion_duration_ms",
    }
    for metric, threshold_name in min_metrics.items():
        if threshold_name not in thresholds:
            continue
        failure = _threshold_failure(
            metric=metric,
            current=metrics.get(metric),
            limit=thresholds[threshold_name],
            direction="min",
        )
        if failure is not None:
            failures.append(failure)
    for metric, threshold_name in max_metrics.items():
        if threshold_name not in thresholds:
            continue
        failure = _threshold_failure(
            metric=metric,
            current=metrics.get(metric),
            limit=thresholds[threshold_name],
            direction="max",
        )
        if failure is not None:
            failures.append(failure)

    report["calibration_profile"] = calibration_profile
    report["thresholds"] = thresholds
    report["gate_failures"] = failures
    report["passed_calibration_gate"] = len(failures) == 0
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval chunks with deterministic local scoring.")
    parser.add_argument("--output-dir", type=Path, required=True, help="pdf2md output directory.")
    parser.add_argument("--eval-set", type=Path, required=True, help="JSON eval set with queries.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-token-target", type=int, default=DEFAULT_CHUNK_TOKEN_TARGET)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--calibration-profile", type=Path, help="JSON file containing profile_name and thresholds.")
    parser.add_argument("--profile-name", default=None, help="Human-readable local calibration profile name.")
    parser.add_argument("--fail-on-threshold", action="store_true", help="Return non-zero when calibration fails.")
    parser.add_argument("--min-hit-at-k", type=float)
    parser.add_argument("--min-mrr", type=float)
    parser.add_argument("--min-citation-coverage", type=float)
    parser.add_argument("--min-expected-source-coverage", type=float)
    parser.add_argument("--min-requirement-coverage", type=float)
    parser.add_argument("--min-table-field-coverage", type=float)
    parser.add_argument("--min-cross-ref-resolved-coverage", type=float)
    parser.add_argument("--min-chunk-size-compliance", type=float)
    parser.add_argument("--min-source-ref-presence-coverage", type=float)
    parser.add_argument("--min-table-contextual-embedding-coverage", type=float)
    parser.add_argument("--min-relationship-target-coverage", type=float)
    parser.add_argument("--max-chunk-token-p95", type=float)
    parser.add_argument("--max-chunk-token-max", type=float)
    parser.add_argument("--max-duplicate-source-ratio", type=float)
    parser.add_argument("--max-conversion-duration-ms", type=float)
    args = parser.parse_args(argv)

    chunks = _read_jsonl(args.output_dir / "retrieval_chunks_rag.jsonl")
    queries = _load_eval_set(args.eval_set)
    report = evaluate_queries(
        chunks=chunks,
        queries=queries,
        top_k=args.top_k,
        chunk_token_target=args.chunk_token_target,
    )
    report["metrics"].update(collect_output_diagnostics(args.output_dir))
    profile_name, thresholds = _profile_thresholds(args.calibration_profile)
    thresholds.update(
        {
            key: value
            for key, value in {
                "min_hit_at_k": args.min_hit_at_k,
                "min_mrr": args.min_mrr,
                "min_citation_coverage": args.min_citation_coverage,
                "min_expected_source_coverage": args.min_expected_source_coverage,
                "min_requirement_coverage": args.min_requirement_coverage,
                "min_table_field_coverage": args.min_table_field_coverage,
                "min_cross_ref_resolved_coverage": args.min_cross_ref_resolved_coverage,
                "min_chunk_size_compliance": args.min_chunk_size_compliance,
                "min_source_ref_presence_coverage": args.min_source_ref_presence_coverage,
                "min_table_contextual_embedding_coverage": args.min_table_contextual_embedding_coverage,
                "min_relationship_target_coverage": args.min_relationship_target_coverage,
                "max_chunk_token_p95": args.max_chunk_token_p95,
                "max_chunk_token_max": args.max_chunk_token_max,
                "max_duplicate_source_ratio": args.max_duplicate_source_ratio,
                "max_conversion_duration_ms": args.max_conversion_duration_ms,
            }.items()
            if value is not None
        }
    )
    if thresholds or args.fail_on_threshold:
        report = apply_calibration_gate(
            report,
            calibration_profile=args.profile_name or profile_name,
            thresholds=thresholds,
        )
    report_path = args.report_path or args.output_dir / "rag_eval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}")
    if args.fail_on_threshold and not report.get("passed_calibration_gate", True):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
