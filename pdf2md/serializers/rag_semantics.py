from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload


PROHIBITED_PATTERN = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|prohibited|shall\s+never)\b",
    re.IGNORECASE,
)
REQUIRED_PATTERN = re.compile(r"\b(?:shall|must|required|mandatory)\b", re.IGNORECASE)
RECOMMENDED_PATTERN = re.compile(r"\b(?:should|recommended)\b", re.IGNORECASE)
OPTIONAL_PATTERN = re.compile(r"\b(?:may(?!\s+(?:\d{1,2}|\d{4})\b)|optional)\b", re.IGNORECASE)
LOW_CONFIDENCE_MODAL_PATTERN = re.compile(r"\b(?:will|can|could|would|expected\s+to|needs\s+to)\b", re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")
DEFINITION_PATTERNS = [
    re.compile(r"^(?P<term>[A-Z][A-Za-z0-9 /_()\-]{1,80})\s*:\s+\S"),
    re.compile(r"^(?P<term>[A-Z][A-Za-z0-9 /_()\-]{1,80})\s+-\s+\S"),
    re.compile(
        r"^(?P<term>[A-Z][A-Za-z0-9 /_()\-]{1,80})\s+"
        r"(?:means|refers\s+to|is\s+defined\s+as)\s+\S",
        re.IGNORECASE,
    ),
]
NOTE_PATTERN = re.compile(r"^\s*NOTE(?:\s+\d+)?\s*[:.-]\s+\S", re.IGNORECASE)
WARNING_PATTERN = re.compile(r"^\s*(?:WARNING|CAUTION|DANGER|IMPORTANT)\s*[:.-]\s+\S", re.IGNORECASE)
LIST_MARKER_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
REFERENCE_PATTERN = re.compile(
    r"\b(?P<kind>Section|Clause|Table|Figure|Appendix)\s+(?P<label>[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*)",
    re.IGNORECASE,
)
NUMERIC_HEADING_PATTERN = re.compile(r"^(?P<label>\d+(?:\.\d+)*)\b")
APPENDIX_HEADING_PATTERN = re.compile(r"^Appendix\s+(?P<label>[A-Za-z0-9]+)\b", re.IGNORECASE)
TABLE_CAPTION_PATTERN = re.compile(r"\bTable\s+(?P<label>[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*)", re.IGNORECASE)
FIGURE_CAPTION_PATTERN = re.compile(r"\bFigure\s+(?P<label>[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*)", re.IGNORECASE)
PARAMETER_HEADER_TOKENS = {
    "bits",
    "command",
    "description",
    "field",
    "name",
    "opcode",
    "parameter",
    "value",
}
PARAMETER_KEY_PRIORITY = ("Field", "Parameter", "Command", "Opcode", "Bits", "Value", "Name")


@dataclass
class SemanticLayerBuildResult:
    semantic_units: list[dict[str, Any]] = field(default_factory=list)
    requirements: list[dict[str, Any]] = field(default_factory=list)
    cross_refs: list[dict[str, Any]] = field(default_factory=list)
    semantic_low_confidence_count: int = 0
    unresolved_cross_ref_count: int = 0
    normative_requirement_count: int = 0


class _SemanticRecorder:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._page_counts: dict[int, int] = {}

    def add(
        self,
        *,
        page: int,
        semantic_type: str,
        text: str,
        source_refs: list[dict[str, Any]],
        page_range: list[int],
        bbox: list[float] | None,
        heading_path: list[str],
        parent_section_id: str | None,
        canonical_key: str | None,
        normative_strength: str,
        confidence: float,
        reasons: list[str],
    ) -> dict[str, Any]:
        self._page_counts[page] = self._page_counts.get(page, 0) + 1
        record = {
            "semantic_id": f"page-{page:04d}-sem-{self._page_counts[page]:04d}",
            "semantic_index": len(self.records) + 1,
            "semantic_type": semantic_type,
            "text": text,
            "source_refs": source_refs,
            "page_range": page_range,
            "bbox": bbox,
            "heading_path": heading_path,
            "parent_section_id": parent_section_id,
            "canonical_key": canonical_key,
            "normative_strength": normative_strength,
            "classification_confidence": round(confidence, 2),
            "classification_reasons": sorted(dict.fromkeys(reasons)),
        }
        self.records.append(record)
        return record


class _CrossRefRecorder:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._page_counts: dict[int, int] = {}

    def add(
        self,
        *,
        page: int,
        source_refs: list[dict[str, Any]],
        source_text: str,
        target_type: str,
        target_label: str,
        target_ref: str | None,
        resolved: bool,
        heading_path: list[str],
        confidence: float,
        reasons: list[str],
    ) -> dict[str, Any]:
        self._page_counts[page] = self._page_counts.get(page, 0) + 1
        record = {
            "ref_id": f"page-{page:04d}-ref-{self._page_counts[page]:04d}",
            "source_refs": source_refs,
            "source_text": source_text,
            "target_type": target_type,
            "target_label": target_label,
            "target_ref": target_ref,
            "resolved": resolved,
            "heading_path": heading_path,
            "classification_confidence": round(confidence, 2),
            "classification_reasons": sorted(dict.fromkeys(reasons)),
        }
        self.records.append(record)
        return record


def _source_ref_for_text_block(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": "text_block",
        "source_id": record.get("block_id"),
        "page": record.get("page"),
        "bbox": record.get("bbox"),
    }


def _source_ref_for_table_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": "table_row",
        "source_id": record.get("table_row_id"),
        "page": record.get("page"),
        "table_id": record.get("table_id"),
        "row_index": record.get("row_index"),
        "bbox": record.get("bbox"),
    }


def _page_of(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _bbox_of(record: dict[str, Any]) -> list[float] | None:
    bbox = record.get("bbox")
    return bbox if isinstance(bbox, list) else None


def _heading_path_of(record: dict[str, Any]) -> list[str]:
    heading_path = record.get("heading_path")
    return [str(item) for item in heading_path] if isinstance(heading_path, list) else []


def _canonical_key(text: str | None) -> str | None:
    if not text:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return normalized[:96] or None


def _split_sentences(text: str) -> list[str]:
    segments: list[str] = []
    for line in text.splitlines() or [text]:
        stripped = line.strip()
        if not stripped:
            continue
        segments.extend(part.strip() for part in SENTENCE_SPLIT_PATTERN.split(stripped) if part.strip())
    return segments or [text.strip()]


def _normative_strength(text: str) -> str | None:
    if PROHIBITED_PATTERN.search(text):
        return "prohibited"
    if REQUIRED_PATTERN.search(text):
        return "required"
    if RECOMMENDED_PATTERN.search(text):
        return "recommended"
    if OPTIONAL_PATTERN.search(text):
        return "optional"
    return None


def _definition_term(text: str) -> str | None:
    for pattern in DEFINITION_PATTERNS:
        match = pattern.search(text.strip())
        if match is not None:
            term = match.group("term").strip(" .:-")
            if len(term.split()) <= 8:
                return term
    return None


def _target_type_for_kind(kind: str) -> str:
    normalized = kind.lower()
    if normalized in {"section", "clause"}:
        return "section"
    if normalized in {"table", "figure", "appendix"}:
        return normalized
    return "unknown"


def _build_reference_targets(
    text_block_records: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    targets: dict[str, dict[str, str]] = {"section": {}, "table": {}, "figure": {}, "appendix": {}}
    for record in text_block_records:
        text = str(record.get("text") or "").strip()
        block_id = str(record.get("block_id") or "")
        if not text or not block_id:
            continue
        if record.get("block_type") == "heading":
            numeric = NUMERIC_HEADING_PATTERN.search(text)
            if numeric is not None:
                targets["section"][numeric.group("label")] = block_id
            appendix = APPENDIX_HEADING_PATTERN.search(text)
            if appendix is not None:
                targets["appendix"][appendix.group("label")] = block_id
        if record.get("block_type") == "caption":
            table = TABLE_CAPTION_PATTERN.search(text)
            if table is not None:
                targets["table"][table.group("label")] = block_id
            figure = FIGURE_CAPTION_PATTERN.search(text)
            if figure is not None:
                targets["figure"][figure.group("label")] = block_id

    for table in rag_tables:
        table_id = str(table.get("table_id") or "")
        caption = str(table.get("caption_text") or "")
        table_match = TABLE_CAPTION_PATTERN.search(caption)
        if table_id and table_match is not None:
            targets["table"][table_match.group("label")] = table_id
    return targets


def _known_parameter_headers(headers: list[Any]) -> bool:
    normalized = {str(header).strip().lower() for header in headers if str(header).strip()}
    return bool(normalized & PARAMETER_HEADER_TOKENS)


def _parameter_key(cells: dict[str, Any]) -> str | None:
    lower_key_map = {str(key).strip().lower(): key for key in cells}
    for preferred in PARAMETER_KEY_PRIORITY:
        key = lower_key_map.get(preferred.lower())
        if key is None:
            continue
        value = str(cells.get(key) or "").strip()
        if value:
            return value
    for value in cells.values():
        text = str(value or "").strip()
        if text:
            return text
    return None


def _reference_source_text(text: str, start: int, end: int) -> str:
    for segment in _split_sentences(text):
        segment_start = text.find(segment)
        if segment_start < 0:
            continue
        segment_end = segment_start + len(segment)
        if segment_start <= start and end <= segment_end:
            return segment
    return text.strip()


def build_semantic_layer(
    *,
    text_block_records: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
) -> SemanticLayerBuildResult:
    """Build deterministic, non-generative semantic sidecars for spec RAG."""
    sorted_text_blocks = sorted(
        text_block_records,
        key=lambda item: (_page_of(item), int(item.get("block_index") or 0)),
    )
    normalized_tables = normalize_rag_table_payload(rag_tables)
    table_records = flatten_rag_table_records(normalized_tables)
    targets = _build_reference_targets(sorted_text_blocks, normalized_tables)
    result = SemanticLayerBuildResult()
    semantic_recorder = _SemanticRecorder()
    cross_ref_recorder = _CrossRefRecorder()
    section_ids_by_block_id: dict[str, str] = {}

    for record in sorted_text_blocks:
        page = _page_of(record)
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        source_refs = [_source_ref_for_text_block(record)]
        heading_path = _heading_path_of(record)
        parent_block_id = record.get("parent_heading_block_id")
        parent_section_id = section_ids_by_block_id.get(str(parent_block_id)) if parent_block_id else None
        bbox = _bbox_of(record)
        page_range = [page, page]
        block_type = str(record.get("block_type") or "paragraph")

        if block_type == "heading":
            section = semantic_recorder.add(
                page=page,
                semantic_type="section",
                text=text,
                source_refs=source_refs,
                page_range=page_range,
                bbox=bbox,
                heading_path=heading_path,
                parent_section_id=parent_section_id,
                canonical_key=_canonical_key(text),
                normative_strength="informative",
                confidence=float(record.get("classification_confidence") or 0.9),
                reasons=["heading_block"],
            )
            section_ids_by_block_id[str(record.get("block_id"))] = section["semantic_id"]
            continue

        if block_type in {"caption", "code", "footnote"}:
            continue

        is_warning = bool(WARNING_PATTERN.search(text))
        is_note = bool(NOTE_PATTERN.search(text))
        if is_warning:
            semantic_recorder.add(
                page=page,
                semantic_type="warning",
                text=text,
                source_refs=source_refs,
                page_range=page_range,
                bbox=bbox,
                heading_path=heading_path,
                parent_section_id=parent_section_id,
                canonical_key=None,
                normative_strength="informative",
                confidence=0.9,
                reasons=["warning_marker"],
            )
        elif is_note:
            semantic_recorder.add(
                page=page,
                semantic_type="note",
                text=text,
                source_refs=source_refs,
                page_range=page_range,
                bbox=bbox,
                heading_path=heading_path,
                parent_section_id=parent_section_id,
                canonical_key=None,
                normative_strength="informative",
                confidence=0.9,
                reasons=["note_marker"],
            )

        term = None if is_warning or is_note else _definition_term(text)
        if term is not None:
            semantic_recorder.add(
                page=page,
                semantic_type="definition",
                text=text,
                source_refs=source_refs,
                page_range=page_range,
                bbox=bbox,
                heading_path=heading_path,
                parent_section_id=parent_section_id,
                canonical_key=_canonical_key(term),
                normative_strength="informative",
                confidence=0.85,
                reasons=["definition_pattern"],
            )

        for segment in _split_sentences(text):
            strength = _normative_strength(segment)
            if strength is None:
                result.semantic_low_confidence_count += int(bool(LOW_CONFIDENCE_MODAL_PATTERN.search(segment)))
                continue
            requirement = semantic_recorder.add(
                page=page,
                semantic_type="requirement",
                text=segment,
                source_refs=source_refs,
                page_range=page_range,
                bbox=bbox,
                heading_path=heading_path,
                parent_section_id=parent_section_id,
                canonical_key=None,
                normative_strength=strength,
                confidence=0.9,
                reasons=["normative_keyword", f"normative_{strength}"],
            )
            result.requirements.append(requirement)
            result.normative_requirement_count += 1

        if block_type == "list":
            for item in [line.strip() for line in text.splitlines() if line.strip()]:
                strength = _normative_strength(item) or "informative"
                semantic_recorder.add(
                    page=page,
                    semantic_type="procedure_step",
                    text=item,
                    source_refs=source_refs,
                    page_range=page_range,
                    bbox=bbox,
                    heading_path=heading_path,
                    parent_section_id=parent_section_id,
                    canonical_key=None,
                    normative_strength=strength,
                    confidence=0.82 if LIST_MARKER_PATTERN.search(item) else 0.72,
                    reasons=["list_item"],
                )

        for match in REFERENCE_PATTERN.finditer(text):
            target_type = _target_type_for_kind(match.group("kind"))
            target_label_value = match.group("label")
            target_ref = targets.get(target_type, {}).get(target_label_value)
            resolved = target_ref is not None
            target_label = f"{match.group('kind')} {target_label_value}"
            source_text = _reference_source_text(text, match.start(), match.end())
            cross_ref_recorder.add(
                page=page,
                source_refs=source_refs,
                source_text=source_text,
                target_type=target_type,
                target_label=target_label,
                target_ref=target_ref,
                resolved=resolved,
                heading_path=heading_path,
                confidence=0.85 if resolved else 0.65,
                reasons=["reference_pattern"] + (["resolved_target"] if resolved else ["unresolved_target"]),
            )
            result.unresolved_cross_ref_count += int(not resolved)
            semantic_recorder.add(
                page=page,
                semantic_type="reference",
                text=source_text,
                source_refs=source_refs,
                page_range=page_range,
                bbox=bbox,
                heading_path=heading_path,
                parent_section_id=parent_section_id,
                canonical_key=_canonical_key(target_label),
                normative_strength="informative",
                confidence=0.8 if resolved else 0.65,
                reasons=["reference_pattern"] + (["resolved_target"] if resolved else ["unresolved_target"]),
            )

    for record in table_records:
        headers = record.get("headers")
        cells = record.get("cells")
        row_text = str(record.get("row_text") or "").strip()
        if not isinstance(headers, list) or not isinstance(cells, dict) or not row_text:
            continue
        page = _page_of(record)
        source_refs = [_source_ref_for_table_row(record)]
        if _known_parameter_headers(headers):
            parameter_key = _parameter_key(cells)
            semantic_recorder.add(
                page=page,
                semantic_type="parameter",
                text=row_text,
                source_refs=source_refs,
                page_range=[page, page],
                bbox=_bbox_of(record),
                heading_path=[],
                parent_section_id=None,
                canonical_key=_canonical_key(parameter_key),
                normative_strength="informative",
                confidence=0.86,
                reasons=["table_parameter_headers"],
            )

        for match in REFERENCE_PATTERN.finditer(row_text):
            target_type = _target_type_for_kind(match.group("kind"))
            target_label_value = match.group("label")
            target_ref = targets.get(target_type, {}).get(target_label_value)
            resolved = target_ref is not None
            target_label = f"{match.group('kind')} {target_label_value}"
            source_text = _reference_source_text(row_text, match.start(), match.end())
            cross_ref_recorder.add(
                page=page,
                source_refs=source_refs,
                source_text=source_text,
                target_type=target_type,
                target_label=target_label,
                target_ref=target_ref,
                resolved=resolved,
                heading_path=[],
                confidence=0.85 if resolved else 0.65,
                reasons=["reference_pattern"] + (["resolved_target"] if resolved else ["unresolved_target"]),
            )
            result.unresolved_cross_ref_count += int(not resolved)

    result.semantic_units = semantic_recorder.records
    result.cross_refs = cross_ref_recorder.records
    return result


def serialize_semantic_units_jsonl(records: list[dict[str, Any]]) -> str:
    return _serialize_jsonl(records)


def serialize_requirements_jsonl(records: list[dict[str, Any]]) -> str:
    return _serialize_jsonl(records)


def serialize_cross_refs_jsonl(records: list[dict[str, Any]]) -> str:
    return _serialize_jsonl(records)


def _serialize_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
