from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pdf2md.serializers.rag_figure_semantics import (
    FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD,
    _region_ocr_result,
    _region_ocr_runtime,
)
from pdf2md.serializers.rag_tables import normalize_rag_table_payload


OCR_EVIDENCE_SCHEMA_VERSION = "1.0"
OCR_EVIDENCE_REASON_TAXONOMY_VERSION = "1.0"
TABLE_OCR_SOURCE_MODES = {"image", "image_only", "page_crop", "ocr", "region_ocr"}


def _page_of(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _bbox(record: dict[str, Any]) -> list[float] | None:
    value = record.get("bbox")
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
    except (TypeError, ValueError):
        return None


def _confidence(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _candidate_text(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return ""
    return str(candidate.get("text") or "").strip()


def _candidate_payload(candidate: Any) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    text = _candidate_text(candidate)
    return {
        "text": text,
        "confidence": _confidence(candidate.get("confidence")),
        "source": str(candidate.get("source") or "region_ocr"),
        "bbox": _bbox(candidate),
        "ocr_confidence_mean": _confidence(candidate.get("ocr_confidence_mean")),
        "ocr_confidence_median": _confidence(candidate.get("ocr_confidence_median")),
        "low_conf_token_ratio": _confidence(candidate.get("low_conf_token_ratio")),
    }


def _source_ref_for_figure(record: dict[str, Any]) -> dict[str, Any]:
    source_type = "figure"
    for ref in record.get("source_refs") or []:
        if isinstance(ref, dict) and ref.get("source_type") in {"figure", "excluded_figure"}:
            source_type = str(ref["source_type"])
            break
    return {
        "source_type": source_type,
        "source_id": str(record.get("figure_id") or ""),
        "page": _page_of(record),
        "bbox": _bbox(record),
    }


def _source_ref_for_table(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": "table",
        "source_id": str(record.get("table_id") or ""),
        "page": _page_of(record),
        "bbox": _bbox(record),
    }


def _region_status(region_ocr: dict[str, Any]) -> str:
    return str(region_ocr.get("status") or "not_attempted")


def _normalized_status(
    *,
    region_status: str,
    candidate: dict[str, Any] | None,
    confidence: float | None,
) -> tuple[str, bool, str | None, str | None]:
    if region_status == "runtime_unavailable":
        return "runtime_unavailable", False, None, "runtime_unavailable"
    if region_status in {"not_attempted", ""}:
        return "not_attempted", False, None, "not_attempted"
    if candidate is None:
        return "rejected", False, None, "empty_result"
    if confidence is None:
        return "rejected", False, None, "missing_confidence"
    if confidence < FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD:
        return "rejected", False, None, "low_confidence"
    return "accepted", True, "confidence_above_threshold", None


def _rejected_reason(region_ocr: dict[str, Any], fallback: str | None) -> str | None:
    if fallback and fallback not in {"empty_result", "runtime_unavailable", "not_attempted"}:
        return fallback
    rejected = region_ocr.get("rejected")
    if isinstance(rejected, dict) and rejected.get("reason"):
        return str(rejected["reason"])
    if region_ocr.get("reason"):
        return str(region_ocr["reason"])
    return fallback


def _region_ocr_from_figure(record: dict[str, Any]) -> dict[str, Any]:
    diagnostics = record.get("figure_region_ocr")
    if not isinstance(diagnostics, dict):
        return {
            "status": "not_attempted",
            "backend": None,
            "ocr_lang": None,
            "attempted": False,
            "reason": "figure_region_ocr_missing",
            "candidate": None,
            "rejected": {"reason": "figure_region_ocr_missing"},
            "report_only": True,
            "text_replaced": False,
        }
    region_ocr = diagnostics.get("region_ocr")
    if not isinstance(region_ocr, dict):
        return {
            "status": "not_attempted",
            "backend": None,
            "ocr_lang": None,
            "attempted": False,
            "reason": "region_ocr_missing",
            "candidate": None,
            "rejected": {"reason": "region_ocr_missing"},
            "report_only": True,
            "text_replaced": False,
        }
    return region_ocr


def _evidence_record(
    *,
    evidence_index: int,
    target_type: str,
    target_id: str,
    page: int,
    bbox: list[float] | None,
    source_sha256: str,
    ocr_backend: str,
    ocr_lang: str,
    region_ocr: dict[str, Any],
    source_ref: dict[str, Any],
) -> dict[str, Any]:
    candidate = _candidate_payload(region_ocr.get("candidate"))
    confidence = _confidence(candidate.get("confidence")) if candidate else None
    status, accepted, accepted_reason, rejected_reason = _normalized_status(
        region_status=_region_status(region_ocr),
        candidate=candidate,
        confidence=confidence,
    )
    rejected_reason = _rejected_reason(region_ocr, rejected_reason)
    ocr_text = _candidate_text(candidate) if accepted and candidate else None
    return {
        "evidence_id": f"ocr-evidence-{evidence_index:06d}",
        "schema_version": OCR_EVIDENCE_SCHEMA_VERSION,
        "reason_taxonomy_version": OCR_EVIDENCE_REASON_TAXONOMY_VERSION,
        "evidence_type": "region_ocr",
        "target_type": target_type,
        "target_id": target_id,
        "page": page,
        "bbox": bbox,
        "source_sha256": source_sha256,
        "ocr_backend": str(region_ocr.get("backend") or ocr_backend),
        "ocr_lang": str(region_ocr.get("ocr_lang") or ocr_lang),
        "status": status,
        "accepted": accepted,
        "accepted_reason": accepted_reason,
        "rejected_reason": rejected_reason,
        "confidence_threshold": FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD,
        "confidence": confidence,
        "ocr_confidence_mean": _confidence(candidate.get("ocr_confidence_mean")) if candidate else None,
        "ocr_confidence_median": _confidence(candidate.get("ocr_confidence_median")) if candidate else None,
        "low_conf_token_ratio": _confidence(candidate.get("low_conf_token_ratio")) if candidate else None,
        "ocr_text": ocr_text,
        "candidate": candidate,
        "rejected": region_ocr.get("rejected") if isinstance(region_ocr.get("rejected"), dict) else None,
        "report_only": True,
        "text_replaced": False,
        "markdown_inserted": False,
        "source_refs": [source_ref],
    }


def _table_region_ocr_eligible(table: dict[str, Any]) -> bool:
    records = table.get("records")
    if not isinstance(records, list) or not records:
        return False
    source_mode = str(table.get("source_mode") or "").strip().lower()
    if source_mode in TABLE_OCR_SOURCE_MODES:
        return True
    return False


def _table_region_ocr_records(
    *,
    rag_tables: list[dict[str, Any]],
    source_sha256: str,
    pdf_path: Path | None,
    ocr_backend: str,
    ocr_lang: str,
    start_index: int,
) -> list[dict[str, Any]]:
    eligible_tables = [
        table
        for table in normalize_rag_table_payload(rag_tables)
        if _table_region_ocr_eligible(table)
    ]
    if not eligible_tables:
        return []

    pdfium_module, backend, runtime_unavailable_reason = (
        _region_ocr_runtime(ocr_backend=ocr_backend) if pdf_path is not None else (None, None, "pdf_path_not_provided")
    )
    document = None
    if pdf_path is not None and runtime_unavailable_reason is None and pdfium_module is not None:
        try:
            document = pdfium_module.PdfDocument(str(pdf_path))
        except Exception:  # noqa: BLE001
            runtime_unavailable_reason = "pdf_open_failed"

    records: list[dict[str, Any]] = []
    try:
        for offset, table in enumerate(
            sorted(eligible_tables, key=lambda item: (_page_of(item), int(item.get("table_index") or 0))),
            start=start_index,
        ):
            region_ocr = _region_ocr_result(
                document=document,
                backend=backend,
                record=table,
                ocr_lang=ocr_lang,
                ocr_backend=ocr_backend,
                runtime_unavailable_reason=runtime_unavailable_reason,
            )
            table_id = str(table.get("table_id") or "")
            records.append(
                _evidence_record(
                    evidence_index=offset,
                    target_type="table",
                    target_id=table_id,
                    page=_page_of(table),
                    bbox=_bbox(table),
                    source_sha256=source_sha256,
                    ocr_backend=ocr_backend,
                    ocr_lang=ocr_lang,
                    region_ocr={
                        **region_ocr,
                        "ocr_lang": ocr_lang,
                        "report_only": True,
                        "text_replaced": False,
                    },
                    source_ref=_source_ref_for_table(table),
                )
            )
    finally:
        if document is not None:
            close = getattr(document, "close", None)
            if close is not None:
                close()
    return records


def build_region_ocr_evidence_records(
    *,
    figure_records: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
    source_sha256: str,
    pdf_path: Path | None = None,
    ocr_backend: str = "tesseract",
    ocr_lang: str = "eng",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build report-only OCR evidence records without mutating Markdown/text sources."""
    records: list[dict[str, Any]] = []
    for figure in sorted(figure_records, key=lambda item: (_page_of(item), int(item.get("figure_index") or 0))):
        figure_id = str(figure.get("figure_id") or "")
        if not figure_id:
            continue
        records.append(
            _evidence_record(
                evidence_index=len(records) + 1,
                target_type="figure",
                target_id=figure_id,
                page=_page_of(figure),
                bbox=_bbox(figure),
                source_sha256=source_sha256,
                ocr_backend=ocr_backend,
                ocr_lang=ocr_lang,
                region_ocr=_region_ocr_from_figure(figure),
                source_ref=_source_ref_for_figure(figure),
            )
        )
    records.extend(
        _table_region_ocr_records(
            rag_tables=rag_tables,
            source_sha256=source_sha256,
            pdf_path=pdf_path,
            ocr_backend=ocr_backend,
            ocr_lang=ocr_lang,
            start_index=len(records) + 1,
        )
    )
    metrics = {
        "figure_ocr_evidence_record_count": len(records),
        "region_ocr_evidence_figure_record_count": sum(1 for record in records if record["target_type"] == "figure"),
        "region_ocr_evidence_table_record_count": sum(1 for record in records if record["target_type"] == "table"),
        "region_ocr_evidence_accepted_count": sum(1 for record in records if record["status"] == "accepted"),
        "region_ocr_evidence_rejected_count": sum(1 for record in records if record["status"] == "rejected"),
        "region_ocr_evidence_runtime_unavailable_count": sum(
            1 for record in records if record["status"] == "runtime_unavailable"
        ),
        "region_ocr_evidence_not_attempted_count": sum(1 for record in records if record["status"] == "not_attempted"),
    }
    return records, metrics


def serialize_region_ocr_evidence_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
