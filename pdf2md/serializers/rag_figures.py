from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.models import ExcludedImageAsset, ImageAsset


def _bbox(value: Any) -> list[float] | None:
    return value if isinstance(value, list) else None


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


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
    return " ".join(parts)


def _figure_kind(text: str) -> tuple[str, list[str], list[str]]:
    lowered = text.lower()
    labels = sorted(dict.fromkeys(re.findall(r"\b(?:[A-Z]{2,}[A-Z0-9_-]*-\d+|[A-Z]{2,}[0-9]+|[A-Z][A-Za-z]+)\b", text)))
    if any(token in lowered for token in ("state machine", "state diagram", "state transition")):
        return "state_machine", labels, ["state_machine_text"]
    if any(token in lowered for token in ("sequence diagram", "message sequence", "timing diagram")):
        return "sequence_diagram", labels, ["sequence_or_timing_text"]
    if any(token in lowered for token in ("register layout", "bit field", "bitfield", "bits ")):
        return "register_layout", labels, ["register_layout_text"]
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
    kind, labels, kind_reasons = _figure_kind(_figure_text(asset.caption_text, asset.alt_text, heading_path))
    return {
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
        "nearby_text_refs": [],
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
    kind, labels, kind_reasons = _figure_kind(
        _figure_text(asset.recovered_text, asset.ocr_candidates, heading_path, asset.parent_heading_index)
    )
    return {
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
