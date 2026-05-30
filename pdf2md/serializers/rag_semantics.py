from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
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
LEGAL_NOTICE_PATTERN = re.compile(
    r"\b(?:all\s+rights\s+reserved|copyright|disclaimer|liabilit(?:y|ies)|license|licensed|"
    r"no\s+part\s+of\s+this\s+publication|permission|proprietary|trademark|warrant(?:y|ies))\b",
    re.IGNORECASE,
)
LEGAL_HEADING_PATTERN = re.compile(r"\b(?:copyright|disclaimer|legal|license|notice|trademark)\b", re.IGNORECASE)
TOC_HEADING_PATTERN = re.compile(r"^\s*(?:table\s+of\s+contents|contents)\s*$", re.IGNORECASE)
TOC_ENTRY_PATTERN = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s+)?(?:[A-Z][\w()/-]+(?:\s+[A-Z0-9][\w()/-]+){0,14}|"
    r"(?:Table|Figure)\s+[A-Za-z0-9.\-]+[:.\s].+?)\s*(?:\.{2,}|\s{3,})\s*\d+\s*$",
    re.IGNORECASE,
)
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
    r"\b(?P<kind>Sections?|Clauses?|Tables?|Figures?|Appendix|Appendices)\s+"
    r"(?P<label>[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*)",
    re.IGNORECASE,
)
MULTI_SECTION_REFERENCE_PATTERN = re.compile(
    r"\b(?P<kind>Sections?|Clauses?)\s+"
    r"(?P<labels>\d+(?:\.\d+)*(?:\s*(?:,|and|or)\s*\d+(?:\.\d+)*)+)",
    re.IGNORECASE,
)
REQUIREMENT_REF_PATTERN = re.compile(
    r"\b(?:Requirement\s+ID|Requirement|Req(?:uirement)?\.?)\s+"
    r"(?P<label>[A-Z][A-Z0-9]{1,12}(?:-[A-Z0-9]{1,12})*-\d+)\b",
    re.IGNORECASE,
)
LOG_IDENTIFIER_REF_PATTERN = re.compile(
    r"\b(?:Log\s+(?:Identifier|Page)|LID)\s+(?P<label>(?:0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h))\b",
    re.IGNORECASE,
)
FEATURE_IDENTIFIER_REF_PATTERN = re.compile(
    r"\b(?:Feature\s+Identifier|FID)\s+(?P<label>(?:0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h))\b",
    re.IGNORECASE,
)
OPCODE_REF_PATTERN = re.compile(
    r"\b(?:Opcode|Command\s+Opcode)\s+(?P<label>(?:0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h))\b",
    re.IGNORECASE,
)
REGISTER_REF_PATTERN = re.compile(
    r"\b(?:Register|Capability)\s+(?P<label>[A-Za-z][A-Za-z0-9 ._/-]{1,80})",
    re.IGNORECASE,
)
LIST_FIGURE_ENTRY_PATTERN = re.compile(
    r"^\s*Figure\s+(?P<label>\d+(?:[.\-]\d+)*)(?P<trailer>[:.\s-].*?)"
    r"(?:\.{2,}|\s{3,})\s*(?P<page>\d+)\s*$",
    re.IGNORECASE,
)
LIST_TABLE_ENTRY_PATTERN = re.compile(
    r"^\s*Table\s+(?P<label>\d+(?:[.\-]\d+)*)(?P<trailer>[:.\s-].*?)"
    r"(?:\.{2,}|\s{3,})\s*(?P<page>\d+)\s*$",
    re.IGNORECASE,
)
REGISTER_IDENTIFIER_SHAPE_PATTERN = re.compile(r"^[A-Z]{2,6}(?:\.[A-Z0-9]{1,12})+$")
EXTERNAL_REFERENCE_PREFIX_PATTERN = re.compile(r"\b(?:RFC|ISO|IEC|PCI(?:e)?|MSI-X)\s+\d*", re.IGNORECASE)
EXTERNAL_REFERENCE_SUFFIX_PATTERN = re.compile(r"\b(?:of|in)\s+(?:RFC|ISO|IEC)\s+\d+", re.IGNORECASE)
REFERENCE_LABEL_STOPWORDS = {
    "above",
    "below",
    "defines",
    "describes",
    "following",
    "in",
    "of",
    "specifies",
}
GENERIC_REGISTER_REFERENCE_LABELS = {
    "level interface",
    "register level interface",
}
GENERIC_REGISTER_REFERENCE_HEADS = {
    "interface",
    "level",
}
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


@dataclass(frozen=True)
class ReferenceCandidate:
    kind: str
    target_type: str
    label: str
    start: int
    end: int


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
        target_key: str | None = None,
        normalized_target_key: str | None = None,
        candidate_count: int = 0,
        unresolved_reason: str | None = None,
    ) -> dict[str, Any]:
        self._page_counts[page] = self._page_counts.get(page, 0) + 1
        record = {
            "ref_id": f"page-{page:04d}-ref-{self._page_counts[page]:04d}",
            "source_refs": source_refs,
            "source_text": source_text,
            "target_type": target_type,
            "target_label": target_label,
            "target_key": target_key,
            "normalized_target_key": normalized_target_key,
            "candidate_count": candidate_count,
            "target_ref": target_ref,
            "resolved": resolved,
            "unresolved_reason": None if resolved else unresolved_reason,
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


def _is_legal_notice(record: dict[str, Any], text: str) -> bool:
    heading_text = " ".join(_heading_path_of(record))
    page = _page_of(record)
    if LEGAL_HEADING_PATTERN.search(heading_text) and LEGAL_NOTICE_PATTERN.search(text):
        return True
    return page <= 5 and LEGAL_NOTICE_PATTERN.search(text) is not None


def _is_toc_noise(record: dict[str, Any], text: str) -> bool:
    heading_path = _heading_path_of(record)
    if any(TOC_HEADING_PATTERN.search(item) for item in heading_path):
        return True
    if TOC_HEADING_PATTERN.search(text):
        return True
    return TOC_ENTRY_PATTERN.search(text) is not None


def _should_skip_requirement_candidates(record: dict[str, Any], text: str) -> bool:
    return _is_legal_notice(record, text) or _is_toc_noise(record, text)


def _definition_term(text: str) -> str | None:
    for pattern in DEFINITION_PATTERNS:
        match = pattern.search(text.strip())
        if match is not None:
            term = match.group("term").strip(" .:-")
            if len(term.split()) <= 8:
                return term
    return None


def _target_type_for_kind(kind: str) -> str:
    normalized = kind.lower().rstrip("s")
    if normalized == "appendice":
        normalized = "appendix"
    if normalized in {"section", "clause"}:
        return "section"
    if normalized in {"table", "figure", "appendix"}:
        return normalized
    return "unknown"


def _target_ref_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def _outline_target_ref(target_type: str, label: str, page: int | None) -> str:
    page_suffix = f"-page-{page:04d}" if page else ""
    return f"pdf-outline-{target_type}-{_target_ref_slug(label)}{page_suffix}"


def _list_target_ref(target_type: str, label: str, page: int | None) -> str:
    page_suffix = f"-page-{page:04d}" if page else ""
    return f"pdf-list-{target_type}-{_target_ref_slug(label)}{page_suffix}"


def _int_or_none(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def extract_pdf_outline_reference_targets(
    reader: Any,
    *,
    selected_pages: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic local reference targets from PDF outline/bookmarks."""
    outline = getattr(reader, "outline", None)
    if outline is None:
        outline = getattr(reader, "outlines", None)
    if not outline:
        return []

    targets: list[dict[str, Any]] = []

    def walk(items: Any) -> None:
        if isinstance(items, (list, tuple)):
            for item in items:
                walk(item)
            return
        title = str(getattr(items, "title", "") or "").strip()
        if not title and isinstance(items, dict):
            title = str(items.get("/Title") or items.get("title") or "").strip()
        if not title:
            return
        page: int | None = None
        try:
            page_index = reader.get_destination_page_number(items)
            if page_index is not None and int(page_index) >= 0:
                page = int(page_index) + 1
        except Exception:  # noqa: BLE001
            page = None
        if selected_pages is not None and page is not None and page not in selected_pages:
            return

        numeric = NUMERIC_HEADING_PATTERN.search(title)
        if numeric is not None:
            label = numeric.group("label")
            targets.append(
                {
                    "target_type": "section",
                    "target_label": label,
                    "target_ref": _outline_target_ref("section", label, page),
                    "page": page,
                    "title": title,
                }
            )
        appendix = APPENDIX_HEADING_PATTERN.search(title)
        if appendix is not None:
            label = appendix.group("label")
            targets.append(
                {
                    "target_type": "appendix",
                    "target_label": label,
                    "target_ref": _outline_target_ref("appendix", label, page),
                    "page": page,
                    "title": title,
                }
            )

    walk(outline)
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for target in targets:
        key = (str(target["target_type"]), str(target["target_label"]))
        deduped.setdefault(key, target)
    return [deduped[key] for key in sorted(deduped)]


def _merge_pdf_outline_targets(
    targets: dict[str, dict[str, str]],
    pdf_outline_targets: list[dict[str, Any]] | None,
) -> None:
    for item in pdf_outline_targets or []:
        target_type = str(item.get("target_type") or "")
        label = str(item.get("target_label") or "").strip()
        if target_type not in targets or not label:
            continue
        target_ref = str(item.get("target_ref") or _outline_target_ref(target_type, label, _int_or_none(item.get("page"))))
        targets[target_type].setdefault(label, target_ref)


def _merge_list_entry_targets(targets: dict[str, dict[str, str]], text: str) -> None:
    for pattern, target_type in ((LIST_FIGURE_ENTRY_PATTERN, "figure"), (LIST_TABLE_ENTRY_PATTERN, "table")):
        match = pattern.search(text)
        if match is None:
            continue
        label = match.group("label")
        page = _int_or_none(match.group("page"))
        targets[target_type].setdefault(label, _list_target_ref(target_type, label, page))


def _build_reference_targets(
    text_block_records: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
    pdf_outline_targets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, str]]:
    targets: dict[str, dict[str, str]] = {
        "section": {},
        "table": {},
        "figure": {},
        "appendix": {},
        "requirement": {},
        "log_page": {},
        "feature": {},
        "opcode": {},
        "register": {},
    }
    for record in text_block_records:
        text = str(record.get("text") or "").strip()
        block_id = str(record.get("block_id") or "")
        if not text or not block_id:
            continue
        _merge_list_entry_targets(targets, text)
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
        for row in table.get("records", []):
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("table_row_id") or "")
            if not row_id:
                continue
            row_text = str(row.get("row_text") or "")
            cells = row.get("cells")
            if isinstance(cells, dict):
                for key, value in cells.items():
                    key_text = str(key)
                    value_text = str(value).strip()
                    if not value_text:
                        continue
                    clean_key = re.sub(r"[^a-z0-9]+", "", key_text.lower())
                    if clean_key in {"requirementid", "requirement", "reqid", "id"}:
                        targets["requirement"][value_text] = row_id
                    elif clean_key in {"logidentifier", "lid", "logpage"}:
                        targets["log_page"][value_text] = row_id
                    elif clean_key in {"featureidentifier", "fid", "feature"}:
                        targets["feature"][value_text] = row_id
                    elif clean_key in {"opcode", "commandopcode"}:
                        targets["opcode"][value_text] = row_id
                    elif clean_key in {"register", "capability", "field"}:
                        targets["register"][value_text] = row_id
            for pattern, target_type in (
                (REQUIREMENT_REF_PATTERN, "requirement"),
                (LOG_IDENTIFIER_REF_PATTERN, "log_page"),
                (FEATURE_IDENTIFIER_REF_PATTERN, "feature"),
                (OPCODE_REF_PATTERN, "opcode"),
            ):
                for match in pattern.finditer(row_text):
                    targets[target_type][match.group("label")] = row_id
    _merge_pdf_outline_targets(targets, pdf_outline_targets)
    return targets


def _canonical_reference_kind(kind: str) -> str:
    normalized = kind.lower()
    if normalized.startswith("section"):
        return "Section"
    if normalized.startswith("clause"):
        return "Clause"
    if normalized.startswith("table"):
        return "Table"
    if normalized.startswith("figure"):
        return "Figure"
    if normalized.startswith("append"):
        return "Appendix"
    return kind.title()


def _normalize_reference_label(kind: str, label: str) -> str | None:
    stripped = label.strip(" .,;:")
    if not stripped:
        return None
    attached = re.fullmatch(r"(?P<base>\d+(?:[.\-]\d+)*)(?P<suffix>[A-Za-z]{3,}.*)", stripped)
    if attached is not None:
        suffix = attached.group("suffix")
        if suffix.lower().startswith(_canonical_reference_kind(kind).lower()):
            return attached.group("base")
        if suffix[:1].islower():
            return None
    return stripped


def _spans_overlap(span: tuple[int, int], existing_spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < existing_end and existing_start < end for existing_start, existing_end in existing_spans)


def _reference_candidates(text: str) -> list[ReferenceCandidate]:
    candidates: list[ReferenceCandidate] = []
    multi_spans: list[tuple[int, int]] = []
    for match in MULTI_SECTION_REFERENCE_PATTERN.finditer(text):
        kind = _canonical_reference_kind(match.group("kind"))
        target_type = _target_type_for_kind(kind)
        labels = re.findall(r"\d+(?:\.\d+)*", match.group("labels"))
        for label in labels:
            candidates.append(
                ReferenceCandidate(kind=kind, target_type=target_type, label=label, start=match.start(), end=match.end())
            )
        multi_spans.append((match.start(), match.end()))

    for match in REFERENCE_PATTERN.finditer(text):
        if _spans_overlap((match.start(), match.end()), multi_spans):
            continue
        kind = _canonical_reference_kind(match.group("kind"))
        label = _normalize_reference_label(kind, match.group("label"))
        if label is None:
            continue
        candidates.append(
            ReferenceCandidate(
                kind=kind,
                target_type=_target_type_for_kind(kind),
                label=label,
                start=match.start(),
                end=match.end(),
            )
        )
    return sorted(candidates, key=lambda item: (item.start, item.end))


def _is_external_or_terminology_reference(text: str, candidate: ReferenceCandidate) -> bool:
    prefix = text[max(0, candidate.start - 40) : candidate.start]
    suffix = text[candidate.end : min(len(text), candidate.end + 40)]
    source_window = text[max(0, candidate.start - 40) : min(len(text), candidate.end + 40)]
    if candidate.target_type in {"appendix", "section"} and (
        EXTERNAL_REFERENCE_PREFIX_PATTERN.search(prefix) or EXTERNAL_REFERENCE_SUFFIX_PATTERN.search(suffix)
    ):
        return True
    if candidate.target_type == "table" and not any(char.isdigit() for char in candidate.label):
        return EXTERNAL_REFERENCE_PREFIX_PATTERN.search(source_window) is not None
    return False


def _target_source_reasons(target_ref: str | None) -> list[str]:
    if not target_ref:
        return []
    if target_ref.startswith("pdf-outline-"):
        return ["target_source_pdf_outline"]
    if target_ref.startswith("pdf-list-"):
        return ["target_source_pdf_list"]
    return []


def _is_register_identifier_label(label: str) -> bool:
    return REGISTER_IDENTIFIER_SHAPE_PATTERN.fullmatch(label.strip(" .,;:")) is not None


def _register_target_exists(targets: dict[str, dict[str, str]], label: str) -> bool:
    target_ref, _, _, _ = _lookup_reference_target(targets, "register", label)
    return target_ref is not None


def _register_reference_label(label: str, targets: dict[str, dict[str, str]]) -> str | None:
    identifier = re.search(r"\b[A-Z]{2,6}(?:\.[A-Z0-9]{1,12})+\b", label)
    if identifier is not None:
        return identifier.group(0)
    trimmed = re.split(r"\s+(?:and|for|in|of|is|shall|must|should|may)\b", label, maxsplit=1)[0].strip()
    if _is_generic_register_reference_label(trimmed):
        return None
    if _is_register_identifier_label(trimmed) or _register_target_exists(targets, trimmed):
        return trimmed
    return None


def _extra_reference_matches(text: str, targets: dict[str, dict[str, str]]) -> list[tuple[re.Match[str], str, str]]:
    matches: list[tuple[re.Match[str], str, str]] = []
    for pattern, target_type, label_prefix in (
        (REQUIREMENT_REF_PATTERN, "requirement", "Requirement"),
        (LOG_IDENTIFIER_REF_PATTERN, "log_page", "Log Identifier"),
        (FEATURE_IDENTIFIER_REF_PATTERN, "feature", "Feature Identifier"),
        (OPCODE_REF_PATTERN, "opcode", "Opcode"),
        (REGISTER_REF_PATTERN, "register", "Register"),
    ):
        for match in pattern.finditer(text):
            label = match.group("label").strip(" .,;:")
            if target_type == "register":
                register_label = _register_reference_label(label, targets)
                if register_label is None:
                    continue
                label = register_label
            if label:
                matches.append((match, target_type, f"{label_prefix} {label}"))
    matches.sort(key=lambda item: item[0].start())
    return matches


def _has_explicit_reference_label_shape(label: str) -> bool:
    stripped = label.strip(" .,;:")
    if not stripped:
        return False
    if any(character.isdigit() for character in stripped):
        return True
    return re.fullmatch(r"[A-Z]{1,4}(?:[.\-][A-Z0-9]{1,8})*", stripped) is not None


def _should_skip_unresolved_reference_candidate(
    *,
    target_type: str,
    target_label_value: str,
    resolved: bool,
) -> bool:
    if resolved:
        return False
    normalized_label = target_label_value.strip(" .,;:").casefold()
    if normalized_label in REFERENCE_LABEL_STOPWORDS:
        return True
    if target_type in {"table", "figure"} and not any(character.isdigit() for character in normalized_label):
        return True
    if target_type in {"section", "clause", "table", "figure"}:
        return not _has_explicit_reference_label_shape(target_label_value)
    return False


def _is_generic_register_reference_label(label: str) -> bool:
    normalized = re.sub(r"\s+", " ", label.strip(" .,;:").casefold())
    if not normalized:
        return True
    if normalized in GENERIC_REGISTER_REFERENCE_LABELS:
        return True
    first_token = normalized.split(" ", 1)[0]
    return first_token in GENERIC_REGISTER_REFERENCE_HEADS


def _target_key_from_label(target_label: str) -> str:
    for prefix in ("Log Identifier ", "Feature Identifier ", "Requirement ", "Opcode ", "Register "):
        if target_label.startswith(prefix):
            return target_label[len(prefix) :]
    parts = target_label.split(" ", 1)
    if len(parts) == 2:
        return parts[1]
    return target_label


def _strip_target_prefixes(value: str) -> str:
    text = value.strip(" .,;:")
    for prefix in (
        "Log Identifier ",
        "Log Page ",
        "LID ",
        "Feature Identifier ",
        "FID ",
        "Requirement ",
        "Req ",
        "Opcode ",
        "Command Opcode ",
        "Register ",
        "Capability ",
    ):
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix) :].strip(" .,;:")
    return text


@lru_cache(maxsize=32768)
def _normalize_ref_key(value: str) -> str:
    text = _strip_target_prefixes(value)
    hex_match = re.fullmatch(r"(?:0x(?P<prefix_hex>[0-9a-fA-F]+)|(?P<suffix_hex>[0-9a-fA-F]+)h|(?P<alpha_hex>[0-9a-fA-F]*[a-fA-F][0-9a-fA-F]*))", text.strip())
    if hex_match is not None:
        value = hex_match.group("prefix_hex") or hex_match.group("suffix_hex") or hex_match.group("alpha_hex") or ""
        return f"hex:{int(value, 16):x}"
    return re.sub(r"[^a-z0-9]+", "", text.lower())


@lru_cache(maxsize=32768)
def _normalized_ref_variants(value: str) -> frozenset[str]:
    text = _strip_target_prefixes(value)
    variants = {_normalize_ref_key(text)}
    trimmed = re.sub(r"\b(?:register|capability|field)\b", " ", text, flags=re.IGNORECASE).strip()
    if trimmed:
        variants.add(_normalize_ref_key(trimmed))
    compact = re.sub(r"\s+", " ", text).strip()
    if compact:
        variants.add(_normalize_ref_key(compact))
    return frozenset(variant for variant in variants if variant)


def _lookup_reference_target(
    targets: dict[str, dict[str, str]],
    target_type: str,
    target_key: str,
) -> tuple[str | None, str, int, str | None]:
    type_targets = targets.get(target_type, {})
    normalized_key = _normalize_ref_key(target_key)
    if target_key in type_targets:
        candidate_refs = {
            ref for label, ref in type_targets.items() if normalized_key in _normalized_ref_variants(label)
        }
        return type_targets[target_key], normalized_key, max(len(candidate_refs), 1), None

    lookup_variants = _normalized_ref_variants(target_key)
    candidate_refs = sorted(
        {
            ref
            for label, ref in type_targets.items()
            if lookup_variants & _normalized_ref_variants(label)
        }
    )
    if len(candidate_refs) == 1:
        return candidate_refs[0], normalized_key, 1, None
    if len(candidate_refs) > 1:
        return None, normalized_key, len(candidate_refs), "ambiguous_target"
    reason = "missing_target_type" if not type_targets else "missing_target_label"
    return None, normalized_key, 0, reason


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
    pdf_outline_targets: list[dict[str, Any]] | None = None,
) -> SemanticLayerBuildResult:
    """Build deterministic, non-generative semantic sidecars for spec RAG."""
    sorted_text_blocks = sorted(
        text_block_records,
        key=lambda item: (_page_of(item), int(item.get("block_index") or 0)),
    )
    normalized_tables = normalize_rag_table_payload(rag_tables)
    table_records = flatten_rag_table_records(normalized_tables)
    targets = _build_reference_targets(sorted_text_blocks, normalized_tables, pdf_outline_targets)
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
        if _should_skip_requirement_candidates(record, text):
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

        for candidate in _reference_candidates(text):
            if _is_external_or_terminology_reference(text, candidate):
                continue
            target_type = candidate.target_type
            target_label_value = candidate.label
            target_ref, normalized_target_key, candidate_count, unresolved_reason = _lookup_reference_target(
                targets,
                target_type,
                target_label_value,
            )
            resolved = target_ref is not None
            if _should_skip_unresolved_reference_candidate(
                target_type=target_type,
                target_label_value=target_label_value,
                resolved=resolved,
            ):
                continue
            target_label = f"{candidate.kind} {target_label_value}"
            source_text = _reference_source_text(text, candidate.start, candidate.end)
            resolved_reasons = _target_source_reasons(target_ref)
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
                reasons=["reference_pattern"]
                + (["resolved_target"] if resolved else ["unresolved_target"])
                + resolved_reasons,
                target_key=target_label_value,
                normalized_target_key=normalized_target_key,
                candidate_count=candidate_count,
                unresolved_reason=unresolved_reason,
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
                reasons=["reference_pattern"]
                + (["resolved_target"] if resolved else ["unresolved_target"])
                + resolved_reasons,
            )

        for match, target_type, target_label in _extra_reference_matches(text, targets):
            target_key = _target_key_from_label(target_label)
            target_ref, normalized_target_key, candidate_count, unresolved_reason = _lookup_reference_target(
                targets,
                target_type,
                target_key,
            )
            resolved = target_ref is not None
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
                confidence=0.82 if resolved else 0.62,
                reasons=["technical_reference_pattern"] + (["resolved_target"] if resolved else ["unresolved_target"]),
                target_key=target_key,
                normalized_target_key=normalized_target_key,
                candidate_count=candidate_count,
                unresolved_reason=unresolved_reason,
            )
            result.unresolved_cross_ref_count += int(not resolved)

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
                heading_path=_heading_path_of(record),
                parent_section_id=None,
                canonical_key=_canonical_key(parameter_key),
                normative_strength="informative",
                confidence=0.86,
                reasons=["table_parameter_headers"],
            )

        for candidate in _reference_candidates(row_text):
            if _is_external_or_terminology_reference(row_text, candidate):
                continue
            target_type = candidate.target_type
            target_label_value = candidate.label
            target_ref, normalized_target_key, candidate_count, unresolved_reason = _lookup_reference_target(
                targets,
                target_type,
                target_label_value,
            )
            resolved = target_ref is not None
            if _should_skip_unresolved_reference_candidate(
                target_type=target_type,
                target_label_value=target_label_value,
                resolved=resolved,
            ):
                continue
            target_label = f"{candidate.kind} {target_label_value}"
            source_text = _reference_source_text(row_text, candidate.start, candidate.end)
            resolved_reasons = _target_source_reasons(target_ref)
            cross_ref_recorder.add(
                page=page,
                source_refs=source_refs,
                source_text=source_text,
                target_type=target_type,
                target_label=target_label,
                target_ref=target_ref,
                resolved=resolved,
                heading_path=_heading_path_of(record),
                confidence=0.85 if resolved else 0.65,
                reasons=["reference_pattern"]
                + (["resolved_target"] if resolved else ["unresolved_target"])
                + resolved_reasons,
                target_key=target_label_value,
                normalized_target_key=normalized_target_key,
                candidate_count=candidate_count,
                unresolved_reason=unresolved_reason,
            )
            result.unresolved_cross_ref_count += int(not resolved)

        for match, target_type, target_label in _extra_reference_matches(row_text, targets):
            target_key = _target_key_from_label(target_label)
            target_ref, normalized_target_key, candidate_count, unresolved_reason = _lookup_reference_target(
                targets,
                target_type,
                target_key,
            )
            resolved = target_ref is not None
            source_text = _reference_source_text(row_text, match.start(), match.end())
            cross_ref_recorder.add(
                page=page,
                source_refs=source_refs,
                source_text=source_text,
                target_type=target_type,
                target_label=target_label,
                target_ref=target_ref,
                resolved=resolved,
                heading_path=_heading_path_of(record),
                confidence=0.82 if resolved else 0.62,
                reasons=["technical_reference_pattern"] + (["resolved_target"] if resolved else ["unresolved_target"]),
                target_key=target_key,
                normalized_target_key=normalized_target_key,
                candidate_count=candidate_count,
                unresolved_reason=unresolved_reason,
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
