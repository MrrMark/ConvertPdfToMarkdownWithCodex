from __future__ import annotations

import json
import re
from typing import Any, Callable

from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload


RAG_CHUNK_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
REGEX_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")
TABLE_CONTEXT_CHUNK_TYPES = {"table_row", "technical_table", "domain_unit"}
TEXT_CHUNK_MERGE_POLICY = "merged_sibling_text_blocks"
TEXT_CHUNK_MERGE_REASON = "sibling_text_merge"
TEXT_CHUNK_MERGE_STRATEGY = "adjacent_text_block_same_section_token_budget"
CHUNK_RELATIONSHIP_STRATEGY = "chunk_group_prev_next_section_anchor"
TokenCounter = Callable[[str], int]


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


def _char_token_estimate(text: str) -> int:
    return max((len(text) + 3) // 4, 1) if text else 0


def _regex_token_estimate(text: str) -> int:
    return len(REGEX_TOKEN_PATTERN.findall(text)) if text else 0


def make_token_counter(tokenizer: str = "char") -> TokenCounter:
    """Return a deterministic token counter for retrieval chunk budgeting."""
    if tokenizer == "regex":
        return _regex_token_estimate
    if tokenizer == "tiktoken-cl100k":
        try:
            import tiktoken  # type: ignore[import-not-found]
        except ImportError:
            return _regex_token_estimate
        encoding = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(encoding.encode(text)) if text else 0
    return _char_token_estimate


def _token_estimate(text: str, token_counter: TokenCounter | None = None) -> int:
    counter = token_counter or _char_token_estimate
    return counter(text)


def _source_ref_key(ref: dict[str, Any]) -> tuple[str, str, str, str]:
    bbox = ref.get("bbox")
    bbox_key = json.dumps(bbox, sort_keys=True, separators=(",", ":")) if bbox is not None else ""
    return (
        str(ref.get("source_type") or ""),
        str(ref.get("source_id") or ""),
        str(ref.get("page") or ""),
        bbox_key,
    )


def _ordered_unique_source_refs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        for ref in record.get("source_refs") or []:
            if not isinstance(ref, dict):
                continue
            key = _source_ref_key(ref)
            if key in seen:
                continue
            seen.add(key)
            refs.append(dict(ref))
    return refs


def _source_dedupe_key(source_refs: list[dict[str, Any]]) -> str | None:
    dedupe_key = "|".join(
        sorted(str(ref.get("source_id")) for ref in source_refs if isinstance(ref, dict) and ref.get("source_id"))
    )
    return dedupe_key or None


def _coerce_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
    except (TypeError, ValueError):
        return None


def _union_bboxes(records: list[dict[str, Any]]) -> list[float] | None:
    boxes = [_coerce_bbox(record.get("bbox")) for record in records]
    if not boxes or any(box is None for box in boxes):
        return None
    valid_boxes = [box for box in boxes if box is not None]
    return [
        min(box[0] for box in valid_boxes),
        min(box[1] for box in valid_boxes),
        max(box[2] for box in valid_boxes),
        max(box[3] for box in valid_boxes),
    ]


def _merge_candidate_key(record: dict[str, Any]) -> tuple[Any, ...] | None:
    if record.get("chunk_type") != "text_block":
        return None
    page_range = record.get("page_range") or []
    try:
        page_range_key = tuple(int(item) for item in page_range)
    except (TypeError, ValueError):
        page_range_key = ()
    return (
        record.get("chunk_group_id"),
        tuple(str(item) for item in record.get("heading_path") or []),
        page_range_key,
        str(record.get("section_path") or ""),
        tuple(str(item) for item in record.get("semantic_types") or []),
    )


def _merge_text_records(records: list[dict[str, Any]], token_counter: TokenCounter | None) -> dict[str, Any]:
    source_refs = _ordered_unique_source_refs(records)
    merged_text = "\n\n".join(str(record.get("text") or "").strip() for record in records if record.get("text"))
    first = dict(records[0])
    first["text"] = merged_text
    first["source_refs"] = source_refs
    first["bbox"] = _union_bboxes(records)
    first["retrieval_priority"] = max(int(record.get("retrieval_priority") or 0) for record in records)
    first["char_count"] = len(merged_text)
    first["token_estimate"] = _token_estimate(merged_text, token_counter)
    first["source_record_count"] = len(source_refs)
    first["source_dedupe_key"] = _source_dedupe_key(source_refs)
    first["chunk_boundary_policy"] = TEXT_CHUNK_MERGE_POLICY
    first["chunk_boundary_reasons"] = sorted(
        dict.fromkeys(
            [
                reason
                for record in records
                for reason in list(record.get("chunk_boundary_reasons") or [])
            ]
            + [TEXT_CHUNK_MERGE_REASON]
        )
    )
    first["merged_source_chunk_ids"] = [str(record.get("chunk_id")) for record in records if record.get("chunk_id")]
    first["merged_source_chunk_count"] = len(records)
    first["merge_strategy"] = TEXT_CHUNK_MERGE_STRATEGY
    for split_field in ("parent_chunk_id", "chunk_part_index", "chunk_part_count"):
        first.pop(split_field, None)
    return first


def _flush_merge_buffer(
    buffer: list[dict[str, Any]],
    output: list[dict[str, Any]],
    token_counter: TokenCounter | None,
) -> None:
    if not buffer:
        return
    if len(buffer) == 1:
        output.append(dict(buffer[0]))
        return
    output.append(_merge_text_records(buffer, token_counter))


def merge_sibling_text_chunks(
    records: list[dict[str, Any]],
    *,
    max_tokens: int = 512,
    token_counter: TokenCounter | None = None,
) -> list[dict[str, Any]]:
    """Merge adjacent text block chunks from the same section when they fit the token budget."""
    if max_tokens <= 0:
        return [dict(record) for record in records]

    merged: list[dict[str, Any]] = []
    buffer: list[dict[str, Any]] = []
    buffer_key: tuple[Any, ...] | None = None

    for record in records:
        candidate_key = _merge_candidate_key(record)
        if candidate_key is None:
            _flush_merge_buffer(buffer, merged, token_counter)
            buffer = []
            buffer_key = None
            merged.append(dict(record))
            continue

        if not buffer:
            buffer = [record]
            buffer_key = candidate_key
            continue

        candidate_text = "\n\n".join(
            [str(item.get("text") or "").strip() for item in buffer] + [str(record.get("text") or "").strip()]
        )
        if candidate_key == buffer_key and _token_estimate(candidate_text, token_counter) <= max_tokens:
            buffer.append(record)
            continue

        _flush_merge_buffer(buffer, merged, token_counter)
        buffer = [record]
        buffer_key = candidate_key

    _flush_merge_buffer(buffer, merged, token_counter)
    for index, record in enumerate(merged, start=1):
        record["chunk_id"] = f"chunk-{index:06d}"
        record["chunk_index"] = index
    return merged


def _append_related_id(related: list[str], chunk_id: str | None, *, self_id: str) -> None:
    if not chunk_id or chunk_id == self_id or chunk_id in related:
        return
    related.append(chunk_id)


def assign_chunk_relationships(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add deterministic neighboring chunk metadata without changing source text."""
    chunks = [dict(record) for record in records]
    section_anchor_by_path: dict[str, str] = {}
    group_indices: dict[str, list[int]] = {}

    for index, chunk in enumerate(chunks):
        chunk_id = str(chunk.get("chunk_id") or "")
        section_path = str(chunk.get("section_path") or "")
        chunk_group_id = str(chunk.get("chunk_group_id") or "")
        if chunk_id and section_path and section_path not in section_anchor_by_path:
            section_anchor_by_path[section_path] = chunk_id
        if chunk_group_id:
            group_indices.setdefault(chunk_group_id, []).append(index)

    for indices in group_indices.values():
        for position, chunk_index in enumerate(indices):
            chunk = chunks[chunk_index]
            if position > 0:
                chunk["previous_chunk_id"] = chunks[indices[position - 1]].get("chunk_id")
            if position + 1 < len(indices):
                chunk["next_chunk_id"] = chunks[indices[position + 1]].get("chunk_id")

    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        section_anchor = section_anchor_by_path.get(str(chunk.get("section_path") or ""))
        related: list[str] = []
        previous_chunk_id = chunk.get("previous_chunk_id")
        next_chunk_id = chunk.get("next_chunk_id")
        _append_related_id(related, str(previous_chunk_id) if previous_chunk_id else None, self_id=chunk_id)
        _append_related_id(related, str(next_chunk_id) if next_chunk_id else None, self_id=chunk_id)
        _append_related_id(related, section_anchor, self_id=chunk_id)
        if section_anchor and section_anchor != chunk_id:
            chunk["section_anchor_chunk_id"] = section_anchor
        if related:
            chunk["related_chunk_ids"] = related
        chunk["relationship_strategy"] = CHUNK_RELATIONSHIP_STRATEGY
    return chunks


def _split_oversized_part(part: str, max_tokens: int, token_counter: TokenCounter) -> list[str]:
    if _token_estimate(part, token_counter) <= max_tokens:
        return [part]
    tokens = re.findall(r"\S+\s*", part)
    if len(tokens) <= 1:
        char_budget = max(max_tokens * 4, 1)
        parts: list[str] = []
        for index in range(0, len(part), char_budget):
            chunk = part[index : index + char_budget].strip()
            if not chunk:
                continue
            if len(chunk) > 1 and _token_estimate(chunk, token_counter) > max_tokens:
                midpoint = max(len(chunk) // 2, 1)
                parts.extend(_split_oversized_part(chunk[:midpoint].strip(), max_tokens, token_counter))
                parts.extend(_split_oversized_part(chunk[midpoint:].strip(), max_tokens, token_counter))
                continue
            parts.append(chunk)
        return parts

    parts: list[str] = []
    current = ""
    for token in tokens:
        candidate = current + token
        if current and _token_estimate(candidate.strip(), token_counter) > max_tokens:
            parts.extend(_split_oversized_part(current.strip(), max_tokens, token_counter))
            current = token
        else:
            current = candidate
    if current.strip():
        parts.extend(_split_oversized_part(current.strip(), max_tokens, token_counter))
    return parts


def _split_text_to_token_budget(
    text: str,
    max_tokens: int,
    token_counter: TokenCounter | None = None,
) -> list[str]:
    stripped = text.strip()
    counter = token_counter or _char_token_estimate
    if not stripped or _token_estimate(stripped, counter) <= max_tokens:
        return [stripped] if stripped else []
    if token_counter is not None:
        return _split_oversized_part(stripped, max_tokens, counter)
    char_budget = max(max_tokens * 4, 1)
    parts: list[str] = []
    start = 0
    while start < len(stripped):
        end = min(start + char_budget, len(stripped))
        if end < len(stripped):
            window = stripped[start:end]
            boundary = -1
            for match in RAG_CHUNK_SENTENCE_BOUNDARY.finditer(window):
                boundary = match.end()
            if boundary < char_budget // 2:
                boundary = max(window.rfind("\n"), window.rfind(" "))
            if boundary >= char_budget // 2:
                end = start + boundary
        part = stripped[start:end].strip()
        if part:
            parts.extend(_split_oversized_part(part, max_tokens, counter))
        start = end
        while start < len(stripped) and stripped[start].isspace():
            start += 1
    return parts


def optimize_retrieval_chunks(
    records: list[dict[str, Any]],
    *,
    max_tokens: int = 512,
    token_counter: TokenCounter | None = None,
) -> list[dict[str, Any]]:
    """Split over-budget RAG chunks deterministically while preserving provenance."""
    if max_tokens <= 0:
        return records

    optimized: list[dict[str, Any]] = []
    for record in records:
        text = str(record.get("text") or "")
        parts = _split_text_to_token_budget(text, max_tokens, token_counter)
        if len(parts) <= 1:
            optimized.append(dict(record))
            continue
        parent_chunk_id = str(record.get("chunk_id") or f"chunk-{len(optimized) + 1:06d}")
        original_dedupe_key = str(record.get("source_dedupe_key") or parent_chunk_id)
        for part_index, part in enumerate(parts, start=1):
            split_record = dict(record)
            split_record["text"] = part
            split_record["char_count"] = len(part)
            split_record["token_estimate"] = _token_estimate(part, token_counter)
            if isinstance(record.get("embedding_text"), str):
                split_record.pop("embedding_text", None)
                split_record.pop("embedding_token_estimate", None)
                split_record.pop("embedding_text_strategy", None)
            split_record["parent_chunk_id"] = parent_chunk_id
            split_record["chunk_part_index"] = part_index
            split_record["chunk_part_count"] = len(parts)
            split_record["source_dedupe_key"] = f"{original_dedupe_key}|part-{part_index:03d}"
            split_record["chunk_boundary_policy"] = "source_record_token_budget"
            split_record["chunk_boundary_reasons"] = sorted(
                dict.fromkeys(list(record.get("chunk_boundary_reasons") or []) + ["token_budget_split"])
            )
            optimized.append(split_record)

    for index, record in enumerate(optimized, start=1):
        record["chunk_id"] = f"chunk-{index:06d}"
        record["chunk_index"] = index
    return optimized


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
    schema_version: str,
    source_sha256: str,
    token_counter: TokenCounter | None = None,
    boundary_reasons: list[str] | None = None,
    chunk_group_id: str | None = None,
    embedding_text: str | None = None,
    embedding_text_strategy: str | None = None,
) -> dict[str, Any]:
    chunk = {
        "chunk_id": f"chunk-{index:06d}",
        "schema_version": schema_version,
        "chunk_index": index,
        "chunk_type": chunk_type,
        "text": text,
        "source_sha256": source_sha256,
        "source_refs": source_refs,
        "page_range": page_range,
        "bbox": bbox,
        "heading_path": heading_path,
        "semantic_types": sorted(dict.fromkeys(semantic_types)),
        "normative_strength": normative_strength,
        "retrieval_priority": retrieval_priority,
        "char_count": len(text),
        "token_estimate": _token_estimate(text, token_counter),
        "section_path": " > ".join(heading_path),
        "chunk_group_id": chunk_group_id,
        "source_record_count": len(source_refs),
        "source_dedupe_key": _source_dedupe_key(source_refs),
        "chunk_boundary_policy": "source_record",
        "chunk_boundary_reasons": sorted(dict.fromkeys(boundary_reasons or ["single_source_record"])),
    }
    if embedding_text and embedding_text != text:
        chunk["embedding_text"] = embedding_text
        chunk["embedding_token_estimate"] = _token_estimate(embedding_text, token_counter)
        chunk["embedding_text_strategy"] = embedding_text_strategy or "contextual_embedding_text"
    return chunk


def _contextual_embedding_text(chunk_type: str, text: str, record: dict[str, Any]) -> str | None:
    if chunk_type not in TABLE_CONTEXT_CHUNK_TYPES:
        return None
    context_parts: list[str] = []
    heading_path = _heading_path(record)
    if heading_path:
        context_parts.append("Section: " + " > ".join(heading_path))
    caption = str(record.get("caption_text") or "").strip()
    if caption:
        context_parts.append(f"Caption: {caption}")
    headers = record.get("headers")
    if isinstance(headers, list) and headers:
        context_parts.append("Headers: " + " | ".join(str(header) for header in headers))
    table_id = record.get("table_id")
    if table_id:
        context_parts.append(f"Table: {table_id}")
    unit_type = record.get("unit_type")
    if unit_type:
        context_parts.append(f"Unit type: {unit_type}")
    if not context_parts:
        return None
    return "\n".join(context_parts + [f"Text: {text}"])


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
    schema_version: str = "1.0",
    source_sha256: str = "",
    max_tokens: int = 512,
    token_counter: TokenCounter | None = None,
    contextual_embedding_text: bool = False,
    merge_sibling_text_blocks: bool = False,
    relationship_metadata: bool = False,
) -> list[dict[str, Any]]:
    """Build deterministic ready-to-index chunks for RAG operations."""
    chunks: list[dict[str, Any]] = []

    def append_chunk(**kwargs: Any) -> None:
        chunks.append(
            _make_chunk(
                index=len(chunks) + 1,
                schema_version=schema_version,
                source_sha256=source_sha256,
                token_counter=token_counter,
                **kwargs,
            )
        )

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
            retrieval_priority=96,
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
            heading_path=_heading_path(record),
            semantic_types=[str(record.get("unit_type") or "technical_table")],
            normative_strength=None,
            retrieval_priority=88,
            boundary_reasons=["technical_table_row_boundary"],
            chunk_group_id=f"technical-table-{record.get('table_id') or 'unknown'}",
            embedding_text=_contextual_embedding_text("technical_table", text, record)
            if contextual_embedding_text
            else None,
            embedding_text_strategy="technical_table_context_prefix",
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
            heading_path=_heading_path(record),
            semantic_types=["table_row"],
            normative_strength=None,
            retrieval_priority=70,
            boundary_reasons=["table_row_boundary"],
            chunk_group_id=f"table-{record.get('table_id') or 'unknown'}",
            embedding_text=_contextual_embedding_text("table_row", text, record) if contextual_embedding_text else None,
            embedding_text_strategy="table_context_prefix",
        )

    if merge_sibling_text_blocks:
        chunks = merge_sibling_text_chunks(chunks, max_tokens=max_tokens, token_counter=token_counter)
    chunks = optimize_retrieval_chunks(chunks, max_tokens=max_tokens, token_counter=token_counter)
    if relationship_metadata:
        chunks = assign_chunk_relationships(chunks)
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
