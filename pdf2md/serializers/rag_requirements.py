from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload


REQ_ID_PATTERN = re.compile(
    r"\b(?:REQ|RQT|SHALL|MUST|OCP|LABL|RETC|SLIFE|EOL|TCG|TCGCE|GLP|SLOG|NVME|PCIe?)[A-Z0-9_-]*-\d+\b",
    re.IGNORECASE,
)
GENERIC_REQ_ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,12}(?:-[A-Z0-9]{1,12})*-\d+\b")
CONDITION_PATTERN = re.compile(r"\b(?:if|when|where|unless|provided that)\b[^.;]*", re.IGNORECASE)
EXCEPTION_PATTERN = re.compile(r"\b(?:except|unless|excluding)\b[^.;]*", re.IGNORECASE)
DEPENDENCY_PATTERN = re.compile(
    r"\b(?:see|per|as specified in|according to)\s+(?:Section|Clause|Table|Figure|Requirement)\s+"
    r"[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)
TEST_HINT_PATTERN = re.compile(
    r"\b(?:verify|test|measure|return|report|set|clear|match|support|shall be|shall not|must)\b",
    re.IGNORECASE,
)


def _clean_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _cell(cells: dict[str, Any], *names: str) -> str | None:
    by_clean_key = {_clean_key(key): value for key, value in cells.items()}
    for name in names:
        value = by_clean_key.get(_clean_key(name))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _page_from_semantic(record: dict[str, Any]) -> int:
    page_range = record.get("page_range")
    if isinstance(page_range, list) and page_range:
        try:
            return int(page_range[0])
        except (TypeError, ValueError):
            pass
    for ref in record.get("source_refs") or []:
        if isinstance(ref, dict):
            try:
                return int(ref.get("page") or 0)
            except (TypeError, ValueError):
                continue
    return 0


def _page(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _requirement_id(text: str, cells: dict[str, Any] | None = None) -> str | None:
    if cells:
        explicit = _cell(cells, "Requirement ID", "Requirement", "Req ID", "ID")
        if explicit:
            match = REQ_ID_PATTERN.search(explicit) or GENERIC_REQ_ID_PATTERN.search(explicit)
            if match:
                return match.group(0)
    match = REQ_ID_PATTERN.search(text) or GENERIC_REQ_ID_PATTERN.search(text)
    return match.group(0) if match else None


def _condition(text: str) -> str | None:
    match = CONDITION_PATTERN.search(text)
    return match.group(0).strip() if match else None


def _exception(text: str) -> str | None:
    match = EXCEPTION_PATTERN.search(text)
    return match.group(0).strip() if match else None


def _dependencies(text: str) -> list[str]:
    return sorted({match.group(0).strip() for match in DEPENDENCY_PATTERN.finditer(text)})


def _testability_hint(text: str) -> str:
    if not TEST_HINT_PATTERN.search(text):
        return "unknown"
    lowered = text.lower()
    if any(token in lowered for token in ("return", "report", "set", "clear", "match", "measure")):
        return "directly_testable"
    if any(token in lowered for token in ("support", "shall be", "shall not", "must")):
        return "conformance_check"
    return "review_required"


def _source_ref_for_table_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": "table_row",
        "source_id": row.get("table_row_id"),
        "page": row.get("page"),
        "table_id": row.get("table_id"),
        "row_index": row.get("row_index"),
        "bbox": row.get("bbox"),
    }


def _trace_record(
    *,
    index: int,
    page: int,
    text: str,
    source_refs: list[dict[str, Any]],
    requirement_id: str | None,
    normative_strength: str,
    heading_path: list[str],
    bbox: list[float] | None,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "trace_id": f"req-trace-{index:06d}",
        "trace_index": index,
        "requirement_id": requirement_id,
        "normative_strength": normative_strength,
        "text": text,
        "condition": _condition(text),
        "applicability": None,
        "dependency_refs": _dependencies(text),
        "exception_text": _exception(text),
        "testability_hint": _testability_hint(text),
        "page_range": [page, page],
        "bbox": bbox,
        "heading_path": heading_path,
        "source_refs": source_refs,
        "classification_confidence": 0.9 if requirement_id else 0.82,
        "classification_reasons": sorted(dict.fromkeys(reasons)),
    }


def build_requirement_traceability_records(
    *,
    requirements: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build deterministic requirement traceability records from semantic and table provenance."""
    records: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str, str]] = set()

    def append(record: dict[str, Any]) -> None:
        key = (
            record.get("requirement_id"),
            str(record.get("text") or ""),
            "|".join(str(ref.get("source_id")) for ref in record.get("source_refs") or [] if isinstance(ref, dict)),
        )
        if key in seen:
            return
        seen.add(key)
        record["trace_id"] = f"req-trace-{len(records) + 1:06d}"
        record["trace_index"] = len(records) + 1
        records.append(record)

    for requirement in sorted(requirements, key=lambda item: int(item.get("semantic_index") or 0)):
        text = str(requirement.get("text") or "").strip()
        if not text:
            continue
        page = _page_from_semantic(requirement)
        append(
            _trace_record(
                index=len(records) + 1,
                page=page,
                text=text,
                source_refs=list(requirement.get("source_refs") or []),
                requirement_id=_requirement_id(text),
                normative_strength=str(requirement.get("normative_strength") or "unknown"),
                heading_path=[str(item) for item in requirement.get("heading_path") or []],
                bbox=requirement.get("bbox") if isinstance(requirement.get("bbox"), list) else None,
                reasons=["semantic_requirement"],
            )
        )

    for row in flatten_rag_table_records(normalize_rag_table_payload(rag_tables)):
        cells = row.get("cells")
        headers = row.get("headers")
        row_text = str(row.get("row_text") or "").strip()
        if not isinstance(cells, dict) or not isinstance(headers, list) or not row_text:
            continue
        req_id = _requirement_id(row_text, cells)
        description = _cell(cells, "Description", "Requirement Description", "Requirement", "Text")
        if not req_id or not description:
            continue
        page = _page(row)
        append(
            _trace_record(
                index=len(records) + 1,
                page=page,
                text=description,
                source_refs=[_source_ref_for_table_row(row)],
                requirement_id=req_id,
                normative_strength="unknown",
                heading_path=[],
                bbox=row.get("bbox") if isinstance(row.get("bbox"), list) else None,
                reasons=["table_requirement_id", "table_description"],
            )
        )
    return records


def serialize_requirement_traceability_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
