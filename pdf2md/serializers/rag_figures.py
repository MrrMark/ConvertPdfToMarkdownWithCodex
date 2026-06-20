from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.models import ExcludedImageAsset, ImageAsset


OCR_LABEL_CONFIDENCE_THRESHOLD = 0.65
LABEL_PATTERN = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9_-]*-\d+|[A-Z]{2,}[0-9]+|[A-Z][A-Za-z]+)\b")


def _bbox(value: Any) -> list[float] | None:
    return value if isinstance(value, list) else None


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


def _local_heading_context(heading_path: list[str]) -> list[str]:
    return [heading_path[-1]] if heading_path else []


def _line_max(record: dict[str, Any]) -> int | None:
    indices = record.get("line_indices")
    if not isinstance(indices, list) or not indices:
        return None
    try:
        return max(int(index) for index in indices)
    except (TypeError, ValueError):
        return None


def _block_top(record: dict[str, Any]) -> float | None:
    bbox = _bbox(record.get("bbox"))
    if not bbox or len(bbox) < 2:
        return None
    try:
        return float(bbox[1])
    except (TypeError, ValueError):
        return None


def _nearby_text_refs(
    *,
    page: int,
    bbox: list[float] | None,
    text_block_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not bbox or len(bbox) < 4:
        return []
    x0, top, x1, bottom = (float(value) for value in bbox[:4])
    refs: list[dict[str, Any]] = []
    for record in text_block_records:
        if int(record.get("page") or 0) != page:
            continue
        record_bbox = _bbox(record.get("bbox"))
        if not record_bbox or len(record_bbox) < 4:
            continue
        record_x0, record_top, record_x1, record_bottom = (float(value) for value in record_bbox[:4])
        center_x = (record_x0 + record_x1) / 2.0
        center_y = (record_top + record_bottom) / 2.0
        if not (x0 <= center_x <= x1 and top <= center_y <= bottom):
            continue
        block_type = str(record.get("block_type") or "")
        if block_type in {"caption", "heading"}:
            continue
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        refs.append(
            {
                "block_id": record.get("block_id"),
                "page": page,
                "block_index": record.get("block_index"),
                "block_type": block_type,
                "text": text,
                "bbox": record_bbox,
            }
        )
    refs.sort(key=lambda item: (int(item.get("block_index") or 0), str(item.get("block_id") or "")))
    return refs


def _nearby_heading_path(
    *,
    page: int,
    anchor_line_index: int | None,
    anchor_top: float | None,
    text_block_records: list[dict[str, Any]],
) -> list[str]:
    page_records = [
        record
        for record in text_block_records
        if int(record.get("page") or 0) == page and _heading_path(record)
    ]
    if not page_records:
        return []

    if anchor_line_index is not None:
        candidates = []
        for record in page_records:
            line_max = _line_max(record)
            if line_max is not None and line_max <= anchor_line_index:
                candidates.append((line_max, int(record.get("block_index") or 0), record))
        if candidates:
            return _heading_path(sorted(candidates, key=lambda item: (item[0], item[1]))[-1][2])

    if anchor_top is not None:
        candidates = []
        for record in page_records:
            block_top = _block_top(record)
            if block_top is not None and block_top <= anchor_top:
                candidates.append((block_top, int(record.get("block_index") or 0), record))
        if candidates:
            return _heading_path(sorted(candidates, key=lambda item: (item[0], item[1]))[-1][2])

    return _heading_path(sorted(page_records, key=lambda item: int(item.get("block_index") or 0))[0])


def _figure_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    text = str(item.get("text") or "").strip()
                    if text:
                        parts.append(text)
                elif isinstance(item, str) and item.strip():
                    parts.append(item.strip())
    return " ".join(parts)


def _labels_from_text(text: str) -> list[str]:
    return sorted(dict.fromkeys(LABEL_PATTERN.findall(text)))


def _confidence(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _ocr_candidate_text(candidate: Any) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get("text") or "").strip()
    return ""


def _ocr_candidate_confidence(candidate: Any) -> float | None:
    if not isinstance(candidate, dict):
        return None
    return _confidence(candidate.get("confidence"))


def _diagram_label_diagnostics(
    *,
    caption_labels: list[str],
    ocr_candidates: list[dict[str, Any]],
    recovered_text: str | None = None,
    recovered_confidence: float | None = None,
) -> tuple[list[str], dict[str, Any]]:
    promoted_labels = list(caption_labels)
    rejected: list[dict[str, Any]] = []
    promoted_ocr_candidates: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, float | None]] = set()

    def append_candidate(candidate: dict[str, Any]) -> None:
        key = (_ocr_candidate_text(candidate), _ocr_candidate_confidence(candidate))
        if key in seen_candidates:
            return
        seen_candidates.add(key)
        all_candidates.append(candidate)

    for candidate in ocr_candidates:
        append_candidate(candidate)
    if recovered_text:
        append_candidate({"text": recovered_text, "confidence": recovered_confidence, "source": "recovered_text"})

    for candidate in all_candidates:
        text = _ocr_candidate_text(candidate)
        labels = _labels_from_text(text)
        confidence = _ocr_candidate_confidence(candidate)
        if not labels:
            rejected.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "reason": "no_label_pattern",
                }
            )
            continue
        if confidence is None or confidence < OCR_LABEL_CONFIDENCE_THRESHOLD:
            rejected.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "labels": labels,
                    "reason": "low_confidence",
                }
            )
            continue
        promoted_ocr_candidates.append({"text": text, "confidence": confidence, "labels": labels})
        for label in labels:
            if label not in promoted_labels:
                promoted_labels.append(label)

    diagnostics = {
        "label_confidence_threshold": OCR_LABEL_CONFIDENCE_THRESHOLD,
        "caption_or_heading_label_count": len(caption_labels),
        "ocr_candidate_count": len(all_candidates),
        "promoted_ocr_candidate_count": len(promoted_ocr_candidates),
        "rejected_ocr_candidate_count": len(rejected),
        "promoted_ocr_candidates": promoted_ocr_candidates,
        "rejected_ocr_candidates": rejected,
    }
    return sorted(dict.fromkeys(promoted_labels)), diagnostics


def _captionless_diagnostics(
    *,
    caption_text: str | None,
    heading_path: list[str],
    nearby_text_refs: list[dict[str, Any]],
    detected_labels: list[str],
    label_diagnostics: dict[str, Any],
) -> dict[str, Any] | None:
    if caption_text:
        return None

    rejection_reasons = ["missing_caption"]
    rejected_candidates = label_diagnostics.get("rejected_ocr_candidates")
    if isinstance(rejected_candidates, list):
        for candidate in rejected_candidates:
            if isinstance(candidate, dict) and candidate.get("reason"):
                rejection_reasons.append(str(candidate["reason"]))
    if not heading_path:
        rejection_reasons.append("missing_heading_path")
    if not nearby_text_refs:
        rejection_reasons.append("no_nearby_text_refs")
    if label_diagnostics.get("ocr_candidate_count") and not label_diagnostics.get("promoted_ocr_candidate_count"):
        rejection_reasons.append("no_promoted_ocr_labels")

    promoted_label_count = len(detected_labels)
    return {
        "caption_present": False,
        "heading_path_present": bool(heading_path),
        "nearby_text_ref_count": len(nearby_text_refs),
        "ocr_candidate_count": int(label_diagnostics.get("ocr_candidate_count") or 0),
        "promoted_label_count": promoted_label_count,
        "status": "captionless_promoted_labels" if promoted_label_count else "captionless_diagnostics_only",
        "rejection_reasons": sorted(dict.fromkeys(rejection_reasons)),
    }


def _figure_kind(text: str) -> tuple[str, list[str], list[str]]:
    lowered = text.lower()
    labels = _labels_from_text(text)
    if any(token in lowered for token in ("register map", "memory map", "address map")):
        return "register_map", labels, ["register_map_text"]
    if any(token in lowered for token in ("register layout", "bit field", "bitfield", "bits ")):
        return "register_layout", labels, ["register_layout_text"]
    if any(token in lowered for token in ("waveform", "signal trace", "timing waveform")):
        return "waveform", labels, ["waveform_text"]
    if any(token in lowered for token in ("block diagram", "architecture diagram", "system architecture")):
        return "block_diagram", labels, ["block_diagram_text"]
    if any(token in lowered for token in ("flow diagram", "flowchart", "process flow")):
        return "flow_diagram", labels, ["flow_diagram_text"]
    if any(token in lowered for token in ("table-like", "table like", "matrix", "grid layout")):
        return "table_like_image", labels, ["table_like_image_text"]
    if any(token in lowered for token in ("state machine", "state diagram", "state transition")):
        return "state_machine", labels, ["state_machine_text"]
    if any(token in lowered for token in ("sequence diagram", "message sequence", "timing diagram")):
        return "sequence_diagram", labels, ["sequence_or_timing_text"]
    if any(token in lowered for token in ("diagram", "flow", "architecture")):
        return "diagram", labels, ["diagram_text"]
    return "image", labels, ["image_asset"]


def _figure_record(
    *,
    figure_id: str,
    figure_index: int,
    asset: ImageAsset,
    text_block_records: list[dict[str, Any]],
) -> dict[str, Any]:
    heading_path = _nearby_heading_path(
        page=asset.page,
        anchor_line_index=asset.anchor_line_index,
        anchor_top=asset.anchor_top,
        text_block_records=text_block_records,
    )
    nearby_text_refs = _nearby_text_refs(page=asset.page, bbox=asset.bbox, text_block_records=text_block_records)
    kind, labels, kind_reasons = _figure_kind(
        _figure_text(asset.caption_text, asset.alt_text, _local_heading_context(heading_path), nearby_text_refs)
    )
    labels, label_diagnostics = _diagram_label_diagnostics(caption_labels=labels, ocr_candidates=[])
    record = {
        "figure_id": figure_id,
        "page": asset.page,
        "figure_index": figure_index,
        "record_type": "image",
        "status": "available",
        "path": asset.path,
        "bbox": asset.bbox,
        "width": asset.width,
        "height": asset.height,
        "caption_text": asset.caption_text,
        "caption_source": asset.caption_source,
        "caption_confidence": asset.caption_confidence,
        "alt_text": asset.alt_text,
        "heading_path": heading_path,
        "source": asset.source,
        "sha256": asset.sha256,
        "dedupe_of": asset.dedupe_of,
        "crop_reason": asset.crop_reason,
        "crop_content_ratio": asset.crop_content_ratio,
        "crop_rejected_reason": asset.crop_rejected_reason,
        "ocr_candidates": [],
        "figure_kind": kind,
        "diagram_candidate": kind != "image",
        "detected_labels": labels,
        "nearby_text_refs": nearby_text_refs,
        "source_refs": [
            {
                "source_type": "figure",
                "source_id": figure_id,
                "page": asset.page,
                "bbox": asset.bbox,
                "path": asset.path,
            }
        ],
        "classification_confidence": round(float(asset.caption_confidence or 0.75), 2),
        "classification_reasons": sorted(dict.fromkeys(["image_asset"] + kind_reasons)),
    }
    if kind != "image":
        record["diagram_label_diagnostics"] = label_diagnostics
    captionless_diagnostics = _captionless_diagnostics(
        caption_text=asset.caption_text,
        heading_path=heading_path,
        nearby_text_refs=nearby_text_refs,
        detected_labels=labels,
        label_diagnostics=label_diagnostics,
    )
    if captionless_diagnostics is not None and (kind != "image" or nearby_text_refs):
        record["captionless_diagnostics"] = captionless_diagnostics
    return record


def _excluded_figure_record(
    *,
    figure_id: str,
    figure_index: int,
    asset: ExcludedImageAsset,
    text_block_records: list[dict[str, Any]],
) -> dict[str, Any]:
    heading_path = _nearby_heading_path(
        page=asset.page,
        anchor_line_index=None,
        anchor_top=None,
        text_block_records=text_block_records,
    )
    reasons = ["excluded_image_asset", str(asset.reason)]
    if asset.recovered_text:
        reasons.append("recovered_text")
    recovered_confidence = _confidence(asset.recovered_confidence)
    candidate_labels, label_diagnostics = _diagram_label_diagnostics(
        caption_labels=[],
        ocr_candidates=asset.ocr_candidates,
        recovered_text=asset.recovered_text,
        recovered_confidence=recovered_confidence,
    )
    promoted_ocr_text = [
        str(candidate.get("text") or "")
        for candidate in label_diagnostics["promoted_ocr_candidates"]
        if isinstance(candidate, dict)
    ]
    kind, labels, kind_reasons = _figure_kind(
        _figure_text(*promoted_ocr_text, _local_heading_context(heading_path), asset.parent_heading_index)
    )
    labels = sorted(dict.fromkeys(labels + candidate_labels))
    record = {
        "figure_id": figure_id,
        "page": asset.page,
        "figure_index": figure_index,
        "record_type": "excluded_image",
        "status": "excluded",
        "path": None,
        "bbox": asset.bbox,
        "width": asset.width,
        "height": asset.height,
        "caption_text": asset.recovered_text,
        "caption_source": asset.recovery_strategy,
        "caption_confidence": asset.recovered_confidence,
        "alt_text": None,
        "heading_path": heading_path,
        "source": asset.classification,
        "sha256": asset.sha256,
        "dedupe_of": None,
        "crop_reason": None,
        "crop_content_ratio": None,
        "crop_rejected_reason": asset.reason,
        "ocr_candidates": asset.ocr_candidates,
        "figure_kind": kind,
        "diagram_candidate": kind != "image",
        "detected_labels": labels,
        "nearby_text_refs": [],
        "source_refs": [
            {
                "source_type": "excluded_figure",
                "source_id": figure_id,
                "page": asset.page,
                "bbox": asset.bbox,
            }
        ],
        "classification_confidence": round(float(asset.recovered_confidence or 0.5), 2),
        "classification_reasons": sorted(dict.fromkeys(reasons + kind_reasons)),
    }
    if asset.ocr_candidates or asset.recovered_text or kind != "image":
        record["diagram_label_diagnostics"] = label_diagnostics
    captionless_diagnostics = _captionless_diagnostics(
        caption_text=asset.recovered_text,
        heading_path=heading_path,
        nearby_text_refs=[],
        detected_labels=labels,
        label_diagnostics=label_diagnostics,
    )
    if captionless_diagnostics is not None and (asset.ocr_candidates or kind != "image" or heading_path):
        record["captionless_diagnostics"] = captionless_diagnostics
    return record


def build_figure_records(
    *,
    images: list[ImageAsset],
    excluded_images: list[ExcludedImageAsset],
    text_block_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build deterministic figure and diagram records for RAG provenance."""
    records: list[dict[str, Any]] = []
    page_counts: dict[int, int] = {}

    entries: list[tuple[int, int, ImageAsset | ExcludedImageAsset]] = []
    entries.extend((asset.page, asset.index, asset) for asset in images)
    entries.extend((asset.page, asset.index, asset) for asset in excluded_images)

    def sort_key(item: tuple[int, int, ImageAsset | ExcludedImageAsset]) -> tuple[int, int, int]:
        page, index, asset = item
        kind_order = 0 if isinstance(asset, ImageAsset) else 1
        return page, kind_order, index

    for page, _, asset in sorted(entries, key=sort_key):
        page_counts[page] = page_counts.get(page, 0) + 1
        figure_index = page_counts[page]
        figure_id = f"page-{page:04d}-figure-{figure_index:04d}"
        if isinstance(asset, ImageAsset):
            records.append(
                _figure_record(
                    figure_id=figure_id,
                    figure_index=figure_index,
                    asset=asset,
                    text_block_records=text_block_records,
                )
            )
        else:
            records.append(
                _excluded_figure_record(
                    figure_id=figure_id,
                    figure_index=figure_index,
                    asset=asset,
                    text_block_records=text_block_records,
                )
            )
    return records


def serialize_figures_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
