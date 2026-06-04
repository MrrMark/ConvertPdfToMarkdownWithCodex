from __future__ import annotations

import json
import re
from typing import Any


FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD = 0.65
FIGURE_SEMANTIC_LOW_CONFIDENCE_THRESHOLD = 0.65
FIGURE_LABEL_PATTERN = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9_-]*-\d+|[A-Z]{2,}[0-9]+|[A-Z][A-Za-z]+)\b")


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


def augment_figure_records_with_region_ocr(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Promote existing figure OCR candidates into deterministic region OCR diagnostics."""
    augmented: list[dict[str, Any]] = []
    attempted_count = 0
    candidate_count = 0
    promoted_label_count = 0
    low_confidence_count = 0

    for record in records:
        updated = dict(record)
        attempted_count += 1
        candidates = _ocr_candidates(record)
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
                rejected.append({"text": text, "confidence": confidence, "labels": labels, "reason": "low_confidence"})
                continue
            promoted_labels.extend(labels)

        promoted_labels = _ordered_unique(promoted_labels)
        if not promoted_labels and candidates:
            low_confidence_count += 1
        promoted_label_count += len(promoted_labels)
        if promoted_labels:
            updated["detected_labels"] = _ordered_unique(_string_list(updated.get("detected_labels")) + promoted_labels)
            reasons = _string_list(updated.get("classification_reasons"))
            updated["classification_reasons"] = sorted(dict.fromkeys(reasons + ["figure_region_ocr_promoted_labels"]))
        updated["figure_region_ocr"] = {
            "enabled": True,
            "source": "existing_figure_ocr_candidates",
            "candidate_count": len(candidates),
            "promoted_label_count": len(promoted_labels),
            "promoted_labels": promoted_labels,
            "rejected_candidate_count": len(rejected),
            "rejected_candidates": rejected,
            "confidence_threshold": FIGURE_REGION_OCR_CONFIDENCE_THRESHOLD,
            "status": "promoted_labels" if promoted_labels else ("no_promoted_labels" if candidates else "no_candidates"),
        }
        augmented.append(updated)

    return augmented, {
        "figure_region_ocr_attempted_count": attempted_count,
        "figure_region_ocr_candidate_count": candidate_count,
        "figure_region_ocr_promoted_label_count": promoted_label_count,
        "figure_region_ocr_low_confidence_count": low_confidence_count,
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
