from __future__ import annotations

import hashlib
from typing import Any

from pdf2md.serializers.rag_tables import normalize_rag_table_payload, stable_table_id


LOW_TABLE_QUALITY_THRESHOLD = 0.55
ACTIONABLE_TABLE_LOW_QUALITY_REASONS = frozenset(
    {
        "CELL_ALIGNMENT_FAILED",
        "HEADER_ALIGNMENT_FAILED",
        "MISSING_SOURCE_REFS",
        "RAG_SIDECAR_MISMATCH",
        "ROW_SPLIT_SUSPECTED",
        "SOURCE_REF_MISSING",
    }
)


def count_table_fallback_reasons(table_fallbacks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fallback in table_fallbacks:
        for reason in fallback.get("reasons", []):
            counts[str(reason)] = counts.get(str(reason), 0) + 1
    return dict(sorted(counts.items()))


def count_low_quality_tables(table_quality: list[dict]) -> int:
    return len(low_quality_table_pages(table_quality, unique=False))


def summarize_table_confidence_v2(table_quality: list[dict]) -> tuple[dict[str, int], float | None]:
    buckets = {"high": 0, "medium": 0, "low": 0}
    scores: list[float] = []
    for item in table_quality:
        bucket = str(item.get("table_confidence_v2_bucket") or "").lower()
        if bucket in buckets:
            buckets[bucket] += 1
        try:
            scores.append(float(item["table_confidence_v2"]))
        except (KeyError, TypeError, ValueError):
            continue
    average = round(sum(scores) / len(scores), 4) if scores else None
    return {key: value for key, value in buckets.items() if value}, average


def _table_quality_score(item: dict) -> float | None:
    try:
        return float(item.get("quality_score", 1.0))
    except (TypeError, ValueError):
        return None


def _table_quality_key(item: dict) -> tuple[int, int] | None:
    try:
        return (int(item.get("page")), int(item.get("table_index")))
    except (TypeError, ValueError):
        return None


def _table_fallback_keys(table_fallbacks: list[dict]) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    for fallback in table_fallbacks:
        key = _table_quality_key(fallback)
        if key is not None:
            keys.add(key)
    return keys


def _is_low_quality_table(item: dict) -> bool:
    score = _table_quality_score(item)
    return score is not None and score < LOW_TABLE_QUALITY_THRESHOLD


def _is_actionable_low_quality_table(item: dict, fallback_keys: set[tuple[int, int]]) -> bool:
    if not _is_low_quality_table(item):
        return False
    if item.get("actionable") is True:
        return True
    if item.get("missing_source_refs") or item.get("sidecar_mismatch"):
        return True
    reasons = {str(reason) for reason in item.get("reasons", [])}
    if reasons & ACTIONABLE_TABLE_LOW_QUALITY_REASONS:
        return True
    mode = str(item.get("mode") or item.get("source_mode") or "").lower()
    if mode == "html" or _table_quality_key(item) in fallback_keys:
        return False
    return item.get("unresolved") is True


def count_actionable_low_quality_tables(
    table_quality: list[dict],
    table_fallbacks: list[dict],
) -> int:
    fallback_keys = _table_fallback_keys(table_fallbacks)
    return sum(1 for item in table_quality if _is_actionable_low_quality_table(item, fallback_keys))


def low_quality_table_pages(
    table_quality: list[dict],
    *,
    unique: bool = True,
    actionable_only: bool = False,
    table_fallbacks: list[dict] | None = None,
) -> list[int]:
    pages: list[int] = []
    fallback_keys = _table_fallback_keys(table_fallbacks or []) if actionable_only else set()
    for item in table_quality:
        if actionable_only:
            if not _is_actionable_low_quality_table(item, fallback_keys):
                continue
        elif not _is_low_quality_table(item):
            continue
        try:
            pages.append(int(item.get("page")))
        except (TypeError, ValueError):
            continue
    return sorted(set(pages)) if unique else pages


def _safe_review_preview(value: object, *, max_chars: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _sha256_text(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _column_placeholder_header_ratio(headers: list[object]) -> float:
    if not headers:
        return 0.0
    placeholder_count = 0
    for header in headers:
        text = str(header).strip().lower()
        if text.startswith("column ") and text.removeprefix("column ").strip().isdigit():
            placeholder_count += 1
    return round(placeholder_count / len(headers), 4)


def _table_id_from_quality_item(item: dict[str, Any]) -> str | None:
    key = _table_quality_key(item)
    if key is None:
        return None
    return stable_table_id(*key)


def _records_by_table_id(rag_tables: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for table in normalize_rag_table_payload(rag_tables):
        table_id = str(table.get("table_id") or "")
        records[table_id] = [dict(record) for record in table.get("records", [])]
    return records


def _headers_by_table_id(rag_tables: list[dict[str, Any]]) -> dict[str, list[object]]:
    headers: dict[str, list[object]] = {}
    for table in normalize_rag_table_payload(rag_tables):
        table_id = str(table.get("table_id") or "")
        value = table.get("headers")
        headers[table_id] = list(value) if isinstance(value, list) else []
    return headers


def _record_count_by_table_id(records: list[dict[str, Any]], id_key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        table_id = str(record.get(id_key) or "")
        if not table_id:
            continue
        counts[table_id] = counts.get(table_id, 0) + 1
    return counts


def _domain_count_by_table_id(domain_units: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in domain_units:
        for source_ref in record.get("source_refs", []):
            if not isinstance(source_ref, dict):
                continue
            table_id = str(source_ref.get("table_id") or "")
            if not table_id:
                continue
            counts[table_id] = counts.get(table_id, 0) + 1
    return counts


def _table_quality_triage_reasons(
    *,
    item: dict[str, Any],
    row_count: int,
    placeholder_ratio: float,
    technical_unit_count: int,
    domain_unit_count: int,
) -> list[str]:
    reasons: list[str] = []
    if row_count == 0:
        reasons.append("no_rag_rows")
    elif row_count >= 2:
        reasons.append("rag_rows_available")
    if placeholder_ratio >= 0.5:
        reasons.append("placeholder_headers")
    if technical_unit_count:
        reasons.append("technical_units_present")
    if domain_unit_count:
        reasons.append("domain_units_present")
    if item.get("header_rows_promoted"):
        reasons.append("header_row_promoted")
    for reason in item.get("reasons", []):
        text = str(reason)
        if text in {"LOW_HEADER_CONFIDENCE", "HEADER_FRAGMENTED", "MERGED_CELL_SUSPECTED"}:
            reasons.append(text.lower())
    return sorted(dict.fromkeys(reasons))


def build_table_quality_review_pack(
    *,
    table_quality: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
    technical_table_records: list[dict[str, Any]],
    domain_units: list[dict[str, Any]],
    table_fallbacks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the debug-only table review pack from table diagnostics and RAG sidecars."""
    records_by_table = _records_by_table_id(rag_tables)
    headers_by_table = _headers_by_table_id(rag_tables)
    technical_counts = _record_count_by_table_id(technical_table_records, "table_id")
    domain_counts = _domain_count_by_table_id(domain_units)
    fallback_keys = _table_fallback_keys(table_fallbacks)
    items: list[dict[str, Any]] = []
    triage_counts: dict[str, int] = {"actionable": 0, "advisory": 0}

    for quality_item in table_quality:
        if not _is_low_quality_table(quality_item):
            continue
        table_id = _table_id_from_quality_item(quality_item)
        if table_id is None:
            continue
        records = records_by_table.get(table_id, [])
        headers = headers_by_table.get(table_id, [])
        sample_row = records[0] if records else {}
        sample_text = sample_row.get("row_text")
        placeholder_ratio = _column_placeholder_header_ratio(headers)
        technical_unit_count = technical_counts.get(table_id, 0)
        domain_unit_count = domain_counts.get(table_id, 0)
        triage_status = "actionable" if _is_actionable_low_quality_table(quality_item, fallback_keys) else "advisory"
        triage_counts[triage_status] += 1
        bbox = quality_item.get("bbox") or sample_row.get("bbox")
        items.append(
            {
                "page": quality_item.get("page"),
                "table_id": table_id,
                "table_index": quality_item.get("table_index"),
                "bbox": bbox,
                "mode": quality_item.get("mode"),
                "quality_score": quality_item.get("quality_score"),
                "table_confidence_v2": quality_item.get("table_confidence_v2"),
                "table_confidence_v2_bucket": quality_item.get("table_confidence_v2_bucket"),
                "table_confidence_v2_reasons": quality_item.get("table_confidence_v2_reasons", []),
                "fallback_reasons": quality_item.get("reasons", []),
                "header_strategy": quality_item.get("rag_header_strategy"),
                "header_confidence": quality_item.get("header_confidence"),
                "row_count": len(records),
                "empty_cell_ratio": quality_item.get("empty_cell_ratio"),
                "column_placeholder_header_ratio": placeholder_ratio,
                "technical_table_unit_count": technical_unit_count,
                "domain_unit_count": domain_unit_count,
                "sample_row_text_sha256": _sha256_text(sample_text),
                "sample_row_text_preview": _safe_review_preview(sample_text),
                "triage_status": triage_status,
                "triage_reasons": _table_quality_triage_reasons(
                    item=quality_item,
                    row_count=len(records),
                    placeholder_ratio=placeholder_ratio,
                    technical_unit_count=technical_unit_count,
                    domain_unit_count=domain_unit_count,
                ),
            }
        )

    return {
        "schema_version": "1.0",
        "item_count": len(items),
        "low_quality_count": len(items),
        "triage_counts": triage_counts,
        "items": items,
    }


def count_caption_linked_tables(table_quality: list[dict]) -> int:
    return sum(1 for item in table_quality if str(item.get("caption_text") or "").strip())
