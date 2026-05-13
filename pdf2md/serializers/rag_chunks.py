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
) -> dict[str, Any]:
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
        )

    return chunks


def serialize_retrieval_chunks_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
