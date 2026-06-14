from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload
from pdf2md.serializers.rag_stable_ids import normalize_seed_text, with_stable_source_metadata


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
NOTE_PATTERN = re.compile(r"^\s*NOTE(?:\s+\d+)?\s*[:.-]\s+\S", re.IGNORECASE)
EXAMPLE_PATTERN = re.compile(r"^\s*examples?\s*[:.-]\s+\S", re.IGNORECASE)
DEFINITION_PATTERN = re.compile(
    r"^\s*[A-Z][A-Za-z0-9 /_()\-]{1,80}\s*(?::|-|\s+(?:means|refers\s+to|is\s+defined\s+as))\s+\S",
    re.IGNORECASE,
)
LEGAL_NOTICE_PATTERN = re.compile(
    r"\b(?:all\s+rights\s+reserved|copyright|disclaimer|liabilit(?:y|ies)|license|licensed|"
    r"no\s+part\s+of\s+this\s+publication|permission|proprietary|trademark|warrant(?:y|ies))\b",
    re.IGNORECASE,
)
FRONT_MATTER_HEADING_PATTERN = re.compile(
    r"\b(?:abstract|copyright|disclaimer|foreword|introduction|legal|license|notices?|preface|trademark)\b",
    re.IGNORECASE,
)
REQUIREMENT_CANDIDATE_STRENGTHS = {"required", "prohibited", "recommended", "optional"}
REVIEW_ONLY_SEMANTIC_TYPES = {"definition", "note", "warning"}


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


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


def _section_path(heading_path: list[str]) -> str:
    return " > ".join(item for item in heading_path if item)


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


def _verification_intent(testability_hint: str) -> str:
    if testability_hint == "directly_testable":
        return "direct_test"
    if testability_hint == "conformance_check":
        return "conformance_check"
    if testability_hint == "review_required":
        return "manual_review"
    return "unknown"


def _source_locator_fields(source_refs: list[dict[str, Any]]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "domain_unit_id": None,
        "technical_table_unit_id": None,
        "table_id": None,
        "table_row_id": None,
    }
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        source_type = str(ref.get("source_type") or "")
        source_id = ref.get("source_id")
        if source_type == "domain_unit" and source_id:
            fields["domain_unit_id"] = source_id
        elif source_type == "technical_table_unit" and source_id:
            fields["technical_table_unit_id"] = source_id
        elif source_type == "table_row":
            if source_id:
                fields["table_row_id"] = source_id
            if ref.get("table_id"):
                fields["table_id"] = ref.get("table_id")
    return fields


def _review_only_kind(record: dict[str, Any], text: str) -> tuple[str, str] | None:
    semantic_type = str(record.get("semantic_type") or "").strip()
    heading_text = " > ".join(_heading_path(record))
    if semantic_type == "note" or NOTE_PATTERN.search(text):
        return "note", "note"
    if semantic_type == "example" or EXAMPLE_PATTERN.search(text):
        return "example", "example"
    if semantic_type in {"definition", "term"} or DEFINITION_PATTERN.search(text):
        return "definition", "definition"
    if semantic_type == "warning":
        return "review_only", "warning"
    if semantic_type in {"front_matter", "legal_notice"} or LEGAL_NOTICE_PATTERN.search(text):
        return "front_matter", "legal_notice"
    if FRONT_MATTER_HEADING_PATTERN.search(heading_text):
        return "front_matter", "front_matter"
    return None


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
    candidate_kind: str,
    is_requirement_candidate: bool,
    exclusion_reason: str | None = None,
    source_sha256: str = "",
) -> dict[str, Any]:
    condition = _condition(text)
    exception = _exception(text)
    dependency_refs = _dependencies(text)
    testability_hint = _testability_hint(text)
    locator_fields = _source_locator_fields(source_refs)
    record = {
        "trace_id": f"req-trace-{index:06d}",
        "trace_index": index,
        "requirement_id": requirement_id,
        "normative_strength": normative_strength,
        "text": text,
        "condition": condition,
        "applicability": None,
        "dependency_refs": dependency_refs,
        "exception_text": exception,
        "testability_hint": testability_hint,
        "page_range": [page, page],
        "bbox": bbox,
        "heading_path": heading_path,
        "source_refs": source_refs,
        "candidate_kind": candidate_kind,
        "is_requirement_candidate": is_requirement_candidate,
        "exclusion_reason": exclusion_reason,
        "domain_unit_id": locator_fields["domain_unit_id"],
        "technical_table_unit_id": locator_fields["technical_table_unit_id"],
        "table_id": locator_fields["table_id"],
        "table_row_id": locator_fields["table_row_id"],
        "section_path": _section_path(heading_path),
        "verification_intent": _verification_intent(testability_hint),
        "conditions": [condition] if condition else [],
        "exceptions": [exception] if exception else [],
        "applicability_hint": None,
        "classification_confidence": 0.9 if requirement_id else 0.82,
        "classification_reasons": sorted(dict.fromkeys(reasons)),
    }
    return with_stable_source_metadata(record, source_sha256=source_sha256)


def build_requirement_traceability_records(
    *,
    requirements: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
    semantic_units: list[dict[str, Any]] | None = None,
    source_sha256: str = "",
) -> list[dict[str, Any]]:
    """Build deterministic requirement traceability records from semantic and table provenance."""
    records: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str, str]] = set()
    review_only_by_text: dict[str, tuple[str, str]] = {}
    for semantic_unit in semantic_units or []:
        text = str(semantic_unit.get("text") or "").strip()
        if not text:
            continue
        kind = _review_only_kind(semantic_unit, text)
        if kind is not None:
            review_only_by_text[normalize_seed_text(text)] = kind

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
        review_only_kind = review_only_by_text.get(normalize_seed_text(text)) or _review_only_kind(requirement, text)
        candidate_kind = review_only_kind[0] if review_only_kind else "normative_requirement"
        is_requirement_candidate = (
            review_only_kind is None
            and str(requirement.get("normative_strength") or "unknown") in REQUIREMENT_CANDIDATE_STRENGTHS
        )
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
                reasons=["semantic_requirement"] + (["review_only_exclusion"] if review_only_kind else []),
                candidate_kind=candidate_kind,
                is_requirement_candidate=is_requirement_candidate,
                exclusion_reason=review_only_kind[1] if review_only_kind else None,
                source_sha256=source_sha256,
            )
        )

    for semantic_unit in sorted(semantic_units or [], key=lambda item: int(item.get("semantic_index") or 0)):
        text = str(semantic_unit.get("text") or "").strip()
        if not text:
            continue
        review_only_kind = _review_only_kind(semantic_unit, text)
        if review_only_kind is None:
            continue
        page = _page_from_semantic(semantic_unit)
        append(
            _trace_record(
                index=len(records) + 1,
                page=page,
                text=text,
                source_refs=list(semantic_unit.get("source_refs") or []),
                requirement_id=_requirement_id(text),
                normative_strength=str(semantic_unit.get("normative_strength") or "informative"),
                heading_path=[str(item) for item in semantic_unit.get("heading_path") or []],
                bbox=semantic_unit.get("bbox") if isinstance(semantic_unit.get("bbox"), list) else None,
                reasons=[
                    "semantic_review_only",
                    f"candidate_kind_{review_only_kind[0]}",
                    f"exclusion_{review_only_kind[1]}",
                ],
                candidate_kind=review_only_kind[0],
                is_requirement_candidate=False,
                exclusion_reason=review_only_kind[1],
                source_sha256=source_sha256,
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
                heading_path=_heading_path(row),
                bbox=row.get("bbox") if isinstance(row.get("bbox"), list) else None,
                reasons=["table_requirement_id", "table_description"],
                candidate_kind="structured_requirement",
                is_requirement_candidate=True,
                source_sha256=source_sha256,
            )
        )
    return records


def serialize_requirement_traceability_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
