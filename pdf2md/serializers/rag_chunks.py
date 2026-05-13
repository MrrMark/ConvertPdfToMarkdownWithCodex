from __future__ import annotations

import json
from typing import Any

from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload


def _page_of(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _page_range_from_record(record: dict[str, Any]) -> list[int]:
    page_range = record.get("page_range")
    if isinstance(page_range, list) and len(page_range) == 2:
        try:
            return [int(page_range[0]), int(page_range[1])]
        except (TypeError, ValueError):
            pass
    page = _page_of(record)
    return [page, page]


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


def _bbox(record: dict[str, Any]) -> list[float] | None:
    value = record.get("bbox")
    return value if isinstance(value, list) else None


def _source_ref(source_type: str, source_id: str | None, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "page": record.get("page"),
        "bbox": _bbox(record),
    }


def _token_estimate(text: str) -> int:
    return max((len(text) + 3) // 4, 1) if text else 0


def _make_chunk(
    *,
    index: int,
    chunk_type: str,
    text: str,
    source_refs: list[dict[str, Any]],
    page_range: list[int],
    bbox: list[float] | None,
    heading_path: list[str],
    semantic_types: list[str],
    normative_strength: str | None,
    retrieval_priority: int,
    boundary_reasons: list[str] | None = None,
    chunk_group_id: str | None = None,
) -> dict[str, Any]:
    dedupe_key = "|".join(
        sorted(str(ref.get("source_id")) for ref in source_refs if isinstance(ref, dict) and ref.get("source_id"))
    )
    return {
        "chunk_id": f"chunk-{index:06d}",
        "chunk_index": index,
        "chunk_type": chunk_type,
        "text": text,
        "source_refs": source_refs,
        "page_range": page_range,
        "bbox": bbox,
        "heading_path": heading_path,
        "semantic_types": sorted(dict.fromkeys(semantic_types)),
        "normative_strength": normative_strength,
        "retrieval_priority": retrieval_priority,
        "char_count": len(text),
        "token_estimate": _token_estimate(text),
        "section_path": " > ".join(heading_path),
        "chunk_group_id": chunk_group_id,
        "source_record_count": len(source_refs),
        "source_dedupe_key": dedupe_key or None,
        "chunk_boundary_policy": "source_record",
        "chunk_boundary_reasons": sorted(dict.fromkeys(boundary_reasons or ["single_source_record"])),
    }


def _semantic_source_refs(record: dict[str, Any], *, source_type: str) -> list[dict[str, Any]]:
    refs = list(record.get("source_refs") or [])
    refs.append(
        {
            "source_type": source_type,
            "source_id": record.get("semantic_id"),
            "page": _page_range_from_record(record)[0],
            "bbox": _bbox(record),
        }
    )
    return refs


def build_retrieval_chunks(
    *,
    text_block_records: list[dict[str, Any]],
    semantic_units: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
    domain_units: list[dict[str, Any]] | None = None,
    requirement_traceability_records: list[dict[str, Any]] | None = None,
    technical_table_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic ready-to-index chunks for RAG operations."""
    chunks: list[dict[str, Any]] = []

    def append_chunk(**kwargs: Any) -> None:
        chunks.append(_make_chunk(index=len(chunks) + 1, **kwargs))

    for record in sorted(text_block_records, key=lambda item: (_page_of(item), int(item.get("block_index") or 0))):
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        append_chunk(
            chunk_type="text_block",
            text=text,
            source_refs=[_source_ref("text_block", record.get("block_id"), record)],
            page_range=[_page_of(record), _page_of(record)],
            bbox=_bbox(record),
            heading_path=_heading_path(record),
            semantic_types=[str(record.get("block_type") or "text_block")],
            normative_strength=None,
            retrieval_priority=50,
            boundary_reasons=["text_block_boundary"],
            chunk_group_id=f"text-page-{_page_of(record):04d}",
        )

    for record in sorted(requirements, key=lambda item: int(item.get("semantic_index") or 0)):
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        append_chunk(
            chunk_type="requirement",
            text=text,
            source_refs=_semantic_source_refs(record, source_type="requirement"),
            page_range=_page_range_from_record(record),
            bbox=_bbox(record),
            heading_path=_heading_path(record),
            semantic_types=["requirement"],
            normative_strength=str(record.get("normative_strength") or "unknown"),
            retrieval_priority=100,
            boundary_reasons=["requirement_boundary"],
            chunk_group_id=f"requirement-page-{_page_range_from_record(record)[0]:04d}",
        )

    for record in sorted(requirement_traceability_records or [], key=lambda item: int(item.get("trace_index") or 0)):
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        append_chunk(
            chunk_type="requirement_trace",
            text=text,
            source_refs=list(record.get("source_refs") or [])
            + [
                {
                    "source_type": "requirement_trace",
                    "source_id": record.get("trace_id"),
                    "page": _page_range_from_record(record)[0],
                    "bbox": _bbox(record),
                }
            ],
            page_range=_page_range_from_record(record),
            bbox=_bbox(record),
            heading_path=_heading_path(record),
            semantic_types=["requirement_trace"],
            normative_strength=str(record.get("normative_strength") or "unknown"),
            retrieval_priority=98,
            boundary_reasons=["traceability_boundary"],
            chunk_group_id=f"requirement-trace-page-{_page_range_from_record(record)[0]:04d}",
        )

    for record in sorted(semantic_units, key=lambda item: int(item.get("semantic_index") or 0)):
        semantic_type = str(record.get("semantic_type") or "semantic_unit")
        if semantic_type == "requirement":
            continue
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        append_chunk(
            chunk_type="semantic_unit",
            text=text,
            source_refs=_semantic_source_refs(record, source_type="semantic_unit"),
            page_range=_page_range_from_record(record),
            bbox=_bbox(record),
            heading_path=_heading_path(record),
            semantic_types=[semantic_type],
            normative_strength=str(record.get("normative_strength") or "unknown"),
            retrieval_priority=80,
            boundary_reasons=["semantic_unit_boundary"],
            chunk_group_id=f"semantic-page-{_page_range_from_record(record)[0]:04d}",
        )

    for record in sorted(domain_units or [], key=lambda item: int(item.get("domain_unit_index") or 0)):
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        append_chunk(
            chunk_type="domain_unit",
            text=text,
            source_refs=list(record.get("source_refs") or [])
            + [
                {
                    "source_type": "domain_unit",
                    "source_id": record.get("domain_unit_id"),
                    "page": _page_range_from_record(record)[0],
                    "bbox": _bbox(record),
                }
            ],
            page_range=_page_range_from_record(record),
            bbox=_bbox(record),
            heading_path=_heading_path(record),
            semantic_types=[str(record.get("unit_type") or "domain_unit")],
            normative_strength=None,
            retrieval_priority=90,
            boundary_reasons=["domain_unit_boundary"],
            chunk_group_id=f"domain-{record.get('domain') or 'unknown'}",
        )

    for record in sorted(technical_table_records or [], key=lambda item: int(item.get("technical_table_unit_index") or 0)):
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        append_chunk(
            chunk_type="technical_table",
            text=text,
            source_refs=list(record.get("source_refs") or [])
            + [
                {
                    "source_type": "technical_table_unit",
                    "source_id": record.get("technical_table_unit_id"),
                    "page": record.get("page"),
                    "bbox": _bbox(record),
                }
            ],
            page_range=[_page_of(record), _page_of(record)],
            bbox=_bbox(record),
            heading_path=[],
            semantic_types=[str(record.get("unit_type") or "technical_table")],
            normative_strength=None,
            retrieval_priority=88,
            boundary_reasons=["technical_table_row_boundary"],
            chunk_group_id=f"technical-table-{record.get('table_id') or 'unknown'}",
        )

    for record in flatten_rag_table_records(normalize_rag_table_payload(rag_tables)):
        text = str(record.get("row_text") or "").strip()
        if not text:
            continue
        append_chunk(
            chunk_type="table_row",
            text=text,
            source_refs=[
                {
                    "source_type": "table_row",
                    "source_id": record.get("table_row_id"),
                    "page": record.get("page"),
                    "table_id": record.get("table_id"),
                    "row_index": record.get("row_index"),
                    "bbox": _bbox(record),
                }
            ],
            page_range=[_page_of(record), _page_of(record)],
            bbox=_bbox(record),
            heading_path=[],
            semantic_types=["table_row"],
            normative_strength=None,
            retrieval_priority=70,
            boundary_reasons=["table_row_boundary"],
            chunk_group_id=f"table-{record.get('table_id') or 'unknown'}",
        )

    return chunks


def build_retrieval_chunk_diagnostics(records: list[dict[str, Any]], *, target_tokens: int = 512) -> dict[str, Any]:
    """Return deterministic chunk quality diagnostics for long-spec RAG operations."""
    token_estimates = [int(record.get("token_estimate") or 0) for record in records]
    source_keys = [str(record.get("source_dedupe_key") or "") for record in records if record.get("source_dedupe_key")]
    duplicate_count = len(source_keys) - len(set(source_keys))
    return {
        "retrieval_chunk_max_token_estimate": max(token_estimates, default=0),
        "retrieval_chunk_average_token_estimate": round(sum(token_estimates) / len(token_estimates), 2)
        if token_estimates
        else 0.0,
        "retrieval_chunk_over_target_count": sum(1 for value in token_estimates if value > target_tokens),
        "retrieval_chunk_duplicate_source_ref_count": duplicate_count,
    }


def serialize_retrieval_chunks_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
