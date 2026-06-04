from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pdf2md.extractors.ocr import _extract_confidence_metrics, _is_language_data_missing
from pdf2md.extractors.ocr_backends import get_ocr_backend

try:
    import pypdfium2 as pdfium
except Exception:  # noqa: BLE001
    pdfium = None


FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD = 0.65
FIGURE_SEMANTIC_LOW_CONFIDENCE_THRESHOLD = 0.65
FIGURE_LABEL_PATTERN = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9_-]*-\d+|[A-Z]{2,}[0-9]+|[A-Z][A-Za-z]+)\b")
REGION_OCR_RENDER_SCALE = 2.0
REGION_OCR_MIN_CROP_PIXELS = 4


def _page_of(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _figure_index(record: dict[str, Any]) -> int:
    try:
        return int(record.get("figure_index") or 0)
    except (TypeError, ValueError):
        return 0


def _bbox(record: dict[str, Any]) -> list[float] | None:
    value = record.get("bbox")
    return value if isinstance(value, list) else None


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _ordered_unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _labels_from_text(text: str) -> list[str]:
    return sorted(dict.fromkeys(FIGURE_LABEL_PATTERN.findall(text)))


def _confidence(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _nearby_texts(record: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for ref in record.get("nearby_text_refs") or []:
        if not isinstance(ref, dict):
            continue
        text = str(ref.get("text") or "").strip()
        if text:
            texts.append(text)
    return texts


def _figure_source_ref(record: dict[str, Any]) -> dict[str, Any]:
    source_type = "figure"
    for ref in record.get("source_refs") or []:
        if isinstance(ref, dict) and ref.get("source_type") in {"figure", "excluded_figure"}:
            source_type = str(ref["source_type"])
            break
    return {
        "source_type": source_type,
        "source_id": record.get("figure_id"),
        "page": record.get("page"),
        "bbox": _bbox(record),
        "figure_id": record.get("figure_id"),
    }


def _ocr_candidates(record: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, float | None]] = set()

    def append(candidate: Any) -> None:
        if not isinstance(candidate, dict):
            return
        text = str(candidate.get("text") or "").strip()
        if not text:
            return
        confidence = _confidence(candidate.get("confidence"))
        key = (text, confidence)
        if key in seen:
            return
        seen.add(key)
        candidates.append({"text": text, "confidence": confidence, "source": candidate.get("source")})

    for candidate in record.get("ocr_candidates") or []:
        append(candidate)
    diagnostics = record.get("diagram_label_diagnostics")
    if isinstance(diagnostics, dict):
        for candidate in diagnostics.get("promoted_ocr_candidates") or []:
            append(candidate)
    return candidates


def _runtime_unavailable_result(reason: str, *, backend: str) -> dict[str, Any]:
    return {
        "status": "runtime_unavailable",
        "backend": backend,
        "reason": reason,
        "attempted": False,
        "candidate": None,
        "rejected": {"reason": reason},
    }


def _region_ocr_runtime(*, ocr_backend: str) -> tuple[object | None, object | None, str | None]:
    if pdfium is None:
        return None, None, "pdfium_unavailable"
    try:
        import pytesseract
    except Exception:  # noqa: BLE001
        pytesseract = None
    try:
        backend = get_ocr_backend(ocr_backend, pytesseract_module=pytesseract)
    except ValueError:
        return None, None, "unsupported_ocr_backend"
    if not backend.is_available():
        return None, None, "dependency_unavailable"
    runtime_error_reason = backend.configure_runtime()
    if runtime_error_reason is not None:
        return None, None, runtime_error_reason
    return pdfium, backend, None


def _crop_box(
    *,
    bbox: list[float] | None,
    image_width: int,
    image_height: int,
    scale: float,
) -> tuple[int, int, int, int] | None:
    if not bbox or len(bbox) < 4:
        return None
    try:
        x0, top, x1, bottom = (float(value) for value in bbox[:4])
    except (TypeError, ValueError):
        return None
    left = max(0, min(image_width, int(round(x0 * scale))))
    upper = max(0, min(image_height, int(round(top * scale))))
    right = max(0, min(image_width, int(round(x1 * scale))))
    lower = max(0, min(image_height, int(round(bottom * scale))))
    if right - left < REGION_OCR_MIN_CROP_PIXELS or lower - upper < REGION_OCR_MIN_CROP_PIXELS:
        return None
    return left, upper, right, lower


def _region_ocr_result(
    *,
    document: object | None,
    backend: object | None,
    record: dict[str, Any],
    ocr_lang: str,
    ocr_backend: str,
    runtime_unavailable_reason: str | None,
) -> dict[str, Any]:
    bbox = _bbox(record)
    if bbox is None:
        return {
            "status": "rejected",
            "backend": ocr_backend,
            "reason": "missing_bbox",
            "attempted": False,
            "candidate": None,
            "rejected": {"reason": "missing_bbox"},
        }
    if runtime_unavailable_reason is not None:
        return _runtime_unavailable_result(runtime_unavailable_reason, backend=ocr_backend)
    if document is None or backend is None:
        return _runtime_unavailable_result("runtime_not_initialized", backend=ocr_backend)

    page = None
    try:
        page = document.get_page(_page_of(record) - 1)
        bitmap = page.render(scale=REGION_OCR_RENDER_SCALE)
        image = bitmap.to_pil()
        crop_box = _crop_box(
            bbox=bbox,
            image_width=int(getattr(image, "width", 0)),
            image_height=int(getattr(image, "height", 0)),
            scale=REGION_OCR_RENDER_SCALE,
        )
        if crop_box is None:
            return {
                "status": "rejected",
                "backend": ocr_backend,
                "reason": "invalid_bbox",
                "attempted": False,
                "candidate": None,
                "rejected": {"reason": "invalid_bbox", "bbox": bbox},
            }
        region_image = image.crop(crop_box)
        backend_result = backend.recognize(region_image, lang=ocr_lang)
        metrics = _extract_confidence_metrics(backend_result.confidence_data)
        confidence = round(metrics.mean / 100.0, 4)
        text = backend_result.text.strip()
        if not text:
            return {
                "status": "rejected",
                "backend": ocr_backend,
                "reason": "empty_result",
                "attempted": True,
                "candidate": None,
                "rejected": {"reason": "empty_result", "confidence": confidence},
            }
        return {
            "status": "candidate",
            "backend": ocr_backend,
            "reason": None,
            "attempted": True,
            "candidate": {
                "text": text,
                "confidence": confidence,
                "source": "region_ocr",
                "bbox": bbox,
                "ocr_confidence_mean": metrics.mean,
                "ocr_confidence_median": metrics.median,
                "low_conf_token_ratio": metrics.low_conf_token_ratio,
            },
            "rejected": None,
        }
    except Exception as exc:  # noqa: BLE001
        reason = "language_data_missing" if _is_language_data_missing(exc) else "ocr_failed"
        return {
            "status": "rejected",
            "backend": ocr_backend,
            "reason": reason,
            "attempted": True,
            "candidate": None,
            "rejected": {"reason": reason},
        }
    finally:
        if page is not None:
            page.close()


def augment_figure_records_with_region_ocr(
    records: list[dict[str, Any]],
    *,
    pdf_path: Path | None = None,
    ocr_lang: str = "eng",
    ocr_backend: str = "tesseract",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Promote figure OCR evidence into deterministic report-only region OCR diagnostics."""
    augmented: list[dict[str, Any]] = []
    attempted_count = 0
    candidate_count = 0
    promoted_label_count = 0
    low_confidence_count = 0
    render_attempted_count = 0
    region_candidate_count = 0
    accepted_region_count = 0
    rejected_region_count = 0
    crop_rejected_count = 0
    runtime_unavailable_count = 0

    pdfium_module, backend, runtime_unavailable_reason = (
        _region_ocr_runtime(ocr_backend=ocr_backend) if pdf_path is not None else (None, None, None)
    )
    document = None
    if pdf_path is not None and runtime_unavailable_reason is None and pdfium_module is not None:
        try:
            document = pdfium_module.PdfDocument(str(pdf_path))
        except Exception:  # noqa: BLE001
            runtime_unavailable_reason = "pdf_open_failed"

    try:
        for record in records:
            updated = dict(record)
            attempted_count += 1
            if pdf_path is None:
                region_result = {
                    "status": "not_attempted",
                    "backend": ocr_backend,
                    "reason": "pdf_path_not_provided",
                    "attempted": False,
                    "candidate": None,
                    "rejected": None,
                }
            else:
                region_result = _region_ocr_result(
                    document=document,
                    backend=backend,
                    record=record,
                    ocr_lang=ocr_lang,
                    ocr_backend=ocr_backend,
                    runtime_unavailable_reason=runtime_unavailable_reason,
                )
            if region_result["attempted"]:
                render_attempted_count += 1
            if region_result["status"] == "candidate" and region_result["candidate"] is not None:
                region_candidate_count += 1
            elif region_result["status"] == "runtime_unavailable":
                runtime_unavailable_count += 1
            elif region_result["status"] == "rejected":
                rejected_region_count += 1
                if region_result.get("reason") in {"missing_bbox", "invalid_bbox"}:
                    crop_rejected_count += 1

            candidates = _ocr_candidates(record)
            if region_result["candidate"] is not None:
                candidates.append(region_result["candidate"])
            candidate_count += len(candidates)
            promoted_labels: list[str] = []
            rejected: list[dict[str, Any]] = []
            for candidate in candidates:
                text = str(candidate.get("text") or "").strip()
                labels = _labels_from_text(text)
                confidence = _confidence(candidate.get("confidence"))
                if not labels:
                    rejected.append({"text": text, "confidence": confidence, "reason": "no_label_pattern"})
                    continue
                if confidence is None or confidence < FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD:
                    rejected.append(
                        {"text": text, "confidence": confidence, "labels": labels, "reason": "low_confidence"}
                    )
                    continue
                promoted_labels.extend(labels)
                if candidate.get("source") == "region_ocr":
                    accepted_region_count += 1

            promoted_labels = _ordered_unique(promoted_labels)
            if not promoted_labels and candidates:
                low_confidence_count += 1
            promoted_label_count += len(promoted_labels)
            if promoted_labels:
                updated["detected_labels"] = _ordered_unique(
                    _string_list(updated.get("detected_labels")) + promoted_labels
                )
                reasons = _string_list(updated.get("classification_reasons"))
                updated["classification_reasons"] = sorted(
                    dict.fromkeys(reasons + ["figure_region_ocr_promoted_labels"])
                )
            updated["figure_region_ocr"] = {
                "enabled": True,
                "source": "existing_figure_ocr_candidates_and_region_ocr",
                "candidate_count": len(candidates),
                "promoted_label_count": len(promoted_labels),
                "promoted_labels": promoted_labels,
                "rejected_candidate_count": len(rejected),
                "rejected_candidates": rejected,
                "confidence_threshold": FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD,
                "status": "promoted_labels"
                if promoted_labels
                else ("no_promoted_labels" if candidates else "no_candidates"),
                "region_ocr": {
                    "status": region_result["status"],
                    "backend": ocr_backend,
                    "ocr_lang": ocr_lang,
                    "attempted": region_result["attempted"],
                    "reason": region_result.get("reason"),
                    "candidate": region_result["candidate"],
                    "rejected": region_result["rejected"],
                    "report_only": True,
                    "text_replaced": False,
                },
            }
            augmented.append(updated)
    finally:
        if document is not None:
            close = getattr(document, "close", None)
            if close is not None:
                close()

    return augmented, {
        "figure_region_ocr_attempted_count": attempted_count,
        "figure_region_ocr_candidate_count": candidate_count,
        "figure_region_ocr_promoted_label_count": promoted_label_count,
        "figure_region_ocr_low_confidence_count": low_confidence_count,
        "figure_region_ocr_render_attempted_count": render_attempted_count,
        "figure_region_ocr_region_candidate_count": region_candidate_count,
        "figure_region_ocr_accepted_region_count": accepted_region_count,
        "figure_region_ocr_rejected_region_count": rejected_region_count,
        "figure_region_ocr_crop_rejected_count": crop_rejected_count,
        "figure_region_ocr_runtime_unavailable_count": runtime_unavailable_count,
    }


def _evidence(record: dict[str, Any]) -> dict[str, Any]:
    caption_text = str(record.get("caption_text") or "").strip()
    heading_path = _heading_path(record)
    detected_labels = _string_list(record.get("detected_labels"))
    nearby_texts = _nearby_texts(record)
    return {
        "caption_text": caption_text,
        "heading_path": heading_path,
        "detected_labels": detected_labels,
        "nearby_texts": nearby_texts,
    }


def _signal_count(evidence: dict[str, Any]) -> int:
    return sum(
        1
        for value in (
            evidence["caption_text"],
            evidence["heading_path"],
            evidence["detected_labels"],
            evidence["nearby_texts"],
        )
        if value
    )


def _semantic_confidence(record: dict[str, Any], evidence: dict[str, Any]) -> float:
    base = 0.42 + (0.1 * _signal_count(evidence))
    if record.get("diagram_candidate"):
        base += 0.08
    caption_confidence = _confidence(record.get("caption_confidence"))
    if caption_confidence is not None:
        base = max(base, min(caption_confidence, 0.92))
    return round(min(base, 0.95), 2)


def _description_text(record: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = ["Generated figure description (context-only)."]
    figure_kind = str(record.get("figure_kind") or "image")
    lines.append(f"Figure kind: {figure_kind}.")
    if evidence["caption_text"]:
        lines.append(f"Caption: {evidence['caption_text']}")
    if evidence["heading_path"]:
        lines.append("Heading path: " + " > ".join(evidence["heading_path"]))
    if evidence["detected_labels"]:
        lines.append("Detected labels: " + " | ".join(evidence["detected_labels"]))
    for nearby_text in evidence["nearby_texts"]:
        lines.append(f"Nearby text: {nearby_text}")
    return "\n".join(lines)


def build_figure_description_records(
    figure_records: list[dict[str, Any]],
    *,
    backend: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build generated figure description records without mutating Markdown source text."""
    records: list[dict[str, Any]] = []
    skipped_no_evidence_count = 0
    for figure_record in sorted(figure_records, key=lambda item: (_page_of(item), _figure_index(item))):
        evidence = _evidence(figure_record)
        if _signal_count(evidence) == 0:
            skipped_no_evidence_count += 1
            continue
        figure_id = str(figure_record.get("figure_id") or f"page-{_page_of(figure_record):04d}-figure-0000")
        description_index = len(records) + 1
        confidence = _semantic_confidence(figure_record, evidence)
        records.append(
            {
                "description_id": f"figure-description-{description_index:06d}",
                "description_index": description_index,
                "figure_id": figure_id,
                "page": _page_of(figure_record),
                "bbox": _bbox(figure_record),
                "heading_path": evidence["heading_path"],
                "figure_kind": str(figure_record.get("figure_kind") or "image"),
                "text": _description_text(figure_record, evidence),
                "generated_text": True,
                "generation_strategy": "deterministic_context_summary",
                "backend": backend,
                "backend_status": "not_invoked_context_only",
                "source_evidence": {
                    "caption_present": bool(evidence["caption_text"]),
                    "heading_path_present": bool(evidence["heading_path"]),
                    "detected_label_count": len(evidence["detected_labels"]),
                    "nearby_text_count": len(evidence["nearby_texts"]),
                    "visual_pixels_interpreted": False,
                },
                "source_refs": [_figure_source_ref(figure_record)],
                "classification_confidence": confidence,
                "classification_reasons": sorted(
                    dict.fromkeys(
                        ["generated_context_summary"]
                        + (["caption"] if evidence["caption_text"] else [])
                        + (["heading_context"] if evidence["heading_path"] else [])
                        + (["detected_labels"] if evidence["detected_labels"] else [])
                        + (["nearby_text"] if evidence["nearby_texts"] else [])
                    )
                ),
            }
        )
    return records, {
        "figure_description_record_count": len(records),
        "figure_description_low_confidence_count": sum(
            1
            for record in records
            if float(record.get("classification_confidence") or 0.0) < FIGURE_SEMANTIC_LOW_CONFIDENCE_THRESHOLD
        ),
        "figure_description_skipped_no_evidence_count": skipped_no_evidence_count,
    }


def _structure_type(record: dict[str, Any], evidence: dict[str, Any]) -> str:
    text = " ".join(
        [str(record.get("figure_kind") or ""), evidence["caption_text"], *evidence["heading_path"], *evidence["nearby_texts"]]
    ).lower()
    if any(token in text for token in ("waveform", "timing diagram", "signal trace", "timing waveform")):
        return "waveform"
    if any(token in text for token in ("circuit", "schematic")):
        return "circuit_diagram"
    if any(token in text for token in ("block diagram", "blockdiagram", "architecture")):
        return "block_diagram"
    figure_kind = str(record.get("figure_kind") or "image")
    return "diagram" if figure_kind == "image" and evidence["detected_labels"] else figure_kind


def _structure_text(structure_type: str, record: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = [f"figure_structure: {structure_type}"]
    if evidence["caption_text"]:
        lines.append(f"caption: {evidence['caption_text']}")
    if evidence["heading_path"]:
        lines.append("heading_path: " + " > ".join(evidence["heading_path"]))
    if evidence["detected_labels"]:
        lines.append("nodes_or_labels: " + " | ".join(evidence["detected_labels"]))
    for nearby_text in evidence["nearby_texts"]:
        lines.append(f"nearby_text: {nearby_text}")
    return "\n".join(lines)


def build_figure_structure_records(figure_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build conservative structure records for image-only semantic retrieval."""
    records: list[dict[str, Any]] = []
    skipped_no_structure_count = 0
    for figure_record in sorted(figure_records, key=lambda item: (_page_of(item), _figure_index(item))):
        evidence = _evidence(figure_record)
        structure_type = _structure_type(figure_record, evidence)
        has_structure_signal = bool(evidence["detected_labels"]) or structure_type not in {"image", ""}
        if not has_structure_signal:
            skipped_no_structure_count += 1
            continue
        figure_id = str(figure_record.get("figure_id") or f"page-{_page_of(figure_record):04d}-figure-0000")
        structure_index = len(records) + 1
        nodes = [
            {
                "node_id": f"{figure_id}-node-{index:03d}",
                "label": label,
                "source": "detected_label",
            }
            for index, label in enumerate(evidence["detected_labels"], start=1)
        ]
        signals = [
            {"signal_id": f"{figure_id}-signal-{index:03d}", "label": node["label"], "source": node["source"]}
            for index, node in enumerate(nodes, start=1)
        ] if structure_type == "waveform" else []
        confidence = _semantic_confidence(figure_record, evidence)
        records.append(
            {
                "structure_id": f"figure-structure-{structure_index:06d}",
                "structure_index": structure_index,
                "figure_id": figure_id,
                "page": _page_of(figure_record),
                "bbox": _bbox(figure_record),
                "heading_path": evidence["heading_path"],
                "figure_kind": str(figure_record.get("figure_kind") or "image"),
                "structure_type": structure_type,
                "nodes": nodes,
                "edges": [],
                "signals": signals,
                "text": _structure_text(structure_type, figure_record, evidence),
                "generated_text": False,
                "derived_from_context": True,
                "source_refs": [_figure_source_ref(figure_record)],
                "classification_confidence": confidence,
                "classification_reasons": sorted(
                    dict.fromkeys(
                        ["figure_structure_context_extraction"]
                        + (["diagram_candidate"] if figure_record.get("diagram_candidate") else [])
                        + (["detected_labels"] if evidence["detected_labels"] else [])
                        + (["nearby_text"] if evidence["nearby_texts"] else [])
                    )
                ),
            }
        )
    return records, {
        "figure_structure_record_count": len(records),
        "figure_structure_low_confidence_count": sum(
            1
            for record in records
            if float(record.get("classification_confidence") or 0.0) < FIGURE_SEMANTIC_LOW_CONFIDENCE_THRESHOLD
        ),
        "figure_structure_skipped_no_structure_count": skipped_no_structure_count,
    }


def serialize_figure_descriptions_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"


def serialize_figure_structures_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
