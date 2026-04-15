from __future__ import annotations

import base64
import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import pdfplumber
from pypdf import PdfReader
from PIL import Image, ImageFilter, ImageOps

from pdf2md.models import ExcludedImageAsset, ImageAsset, ImageMode, WarningEntry
from pdf2md.utils.structure import extract_leading_heading_index, is_caption_candidate

logger = logging.getLogger(__name__)


@dataclass
class ImageBlock:
    page: int
    index: int
    markdown: str
    top: float
    anchor_line_index: int
    bbox: tuple[float, float, float, float] | None


@dataclass
class ImageExtractionResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    assets: list[ImageAsset] = field(default_factory=list)
    excluded_assets: list[ExcludedImageAsset] = field(default_factory=list)
    blocks_by_page: dict[int, list[ImageBlock]] = field(default_factory=dict)
    structure_recoveries: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class StructureOcrCandidate:
    text: str
    confidence: float | None
    votes: int


@dataclass(frozen=True)
class StructureRecoveryDecision:
    text: str | None
    confidence: float | None
    reason: str
    recovery_strategy: str | None
    context_validated: bool
    parent_heading_index: str | None
    source_candidates: list[dict]


@dataclass(frozen=True)
class PendingStructureMarker:
    page: int
    index: int
    top: float
    bbox: list[float] | None
    width: int | None
    height: int | None
    sha256: str
    title_text: str
    title_top: float
    parent_heading_index: str | None
    child_heading_index: str | None
    ocr_candidates: list[StructureOcrCandidate]


def _guess_extension(image_name: str) -> str:
    lower = image_name.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "jpg"
    if lower.endswith(".png"):
        return "png"
    if lower.endswith(".tif") or lower.endswith(".tiff"):
        return "tiff"
    return "png"


def _build_markdown(
    mode: ImageMode,
    alt_text: str,
    rel_path: str,
    extension: str,
    data: bytes,
    page: int,
    index: int,
) -> str:
    if mode == ImageMode.PLACEHOLDER:
        return f"<!-- image: page={page} index={index} mode=placeholder path={rel_path} -->"
    if mode == ImageMode.EMBEDDED:
        mime = "image/jpeg" if extension in {"jpg", "jpeg"} else "image/png"
        encoded = base64.b64encode(data).decode("ascii")
        return f"![{alt_text}](data:{mime};base64,{encoded})"
    return f"![{alt_text}](./{rel_path})"


def _image_dimensions(image) -> tuple[int | None, int | None]:
    ref = getattr(image, "indirect_reference", None)
    if ref is None:
        return None, None
    width = ref.get("/Width") if isinstance(ref, dict) else None
    height = ref.get("/Height") if isinstance(ref, dict) else None
    try:
        return int(width) if width is not None else None, int(height) if height is not None else None
    except Exception:  # noqa: BLE001
        return None, None


def _is_caption_nearby(lines: list[dict], top: float, bottom: float) -> bool:
    for line in lines:
        line_top = float(line.get("top", 0.0))
        if top - 28 <= line_top <= bottom + 28:
            text = str(line.get("text", "")).strip()
            if is_caption_candidate(text):
                return True
    return False


def _extract_caption_text(lines: list[dict], top: float, bottom: float) -> str | None:
    caption_candidates: list[tuple[float, str]] = []
    for line in lines:
        line_top = float(line.get("top", 0.0))
        if top - 28 <= line_top <= bottom + 36:
            text = str(line.get("text", "")).strip()
            if is_caption_candidate(text):
                caption_candidates.append((abs(line_top - bottom), text))
    if not caption_candidates:
        return None
    caption_candidates.sort(key=lambda item: (item[0], item[1]))
    return caption_candidates[0][1]


def _find_structure_title(lines: list[dict], bbox: list[float] | None) -> dict | None:
    if bbox is None:
        return None
    x0, top, x1, bottom = bbox
    candidates: list[tuple[float, dict]] = []
    for line in lines:
        line_top = float(line.get("top", 0.0))
        line_x0 = float(line.get("x0", 0.0))
        text = str(line.get("text", "")).strip()
        if not text:
            continue
        if line_x0 <= x1 + 8:
            continue
        if line_x0 > 160:
            continue
        if not (top - 8 <= line_top <= bottom + 10):
            continue
        if len(text) > 48:
            continue
        if text.endswith((".", ":")):
            continue
        if text.lower().startswith(("figure ", "fig. ", "table ", "표 ", "그림 ")):
            continue
        if "  " in text:
            continue
        candidates.append((abs(line_top - top), line))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], float(item[1].get("x0", 0.0))))
    return candidates[0][1]


def _find_parent_heading_index(lines: list[dict], title_line: dict | None) -> str | None:
    if title_line is None:
        return None
    title_top = float(title_line.get("top", 0.0))
    best_heading: tuple[float, str] | None = None
    for line in lines:
        line_top = float(line.get("top", 0.0))
        if line_top >= title_top:
            continue
        heading_index = extract_leading_heading_index(str(line.get("text", "")))
        if not heading_index or "." not in heading_index:
            continue
        score = title_top - line_top
        if best_heading is None or score < best_heading[0]:
            best_heading = (score, heading_index)
    return best_heading[1] if best_heading is not None else None


def _find_child_heading_index(
    page_text_lines: dict[int, list[dict]],
    page_number: int,
    title_line: dict | None,
) -> str | None:
    if title_line is None:
        return None
    title_top = float(title_line.get("top", 0.0))
    for candidate_page in sorted(page_text_lines):
        if candidate_page < page_number:
            continue
        for line in page_text_lines[candidate_page]:
            line_top = float(line.get("top", 0.0))
            if candidate_page == page_number and line_top <= title_top:
                continue
            heading_index = extract_leading_heading_index(str(line.get("text", "")))
            if heading_index is None or "." not in heading_index:
                continue
            return heading_index
    return None


def _is_structure_marker_candidate(
    *,
    bbox: list[float] | None,
    width: int | None,
    height: int | None,
    title_line: dict | None,
) -> bool:
    if bbox is None or title_line is None:
        return False
    x0, top, x1, _ = bbox
    if x0 > 90:
        return False
    if (width or 0) > 28 or (height or 0) > 12:
        return False
    title_x0 = float(title_line.get("x0", 0.0))
    if title_x0 < x1 + 10:
        return False
    return 90 <= top <= 680


def _prepare_structure_marker_variants(image_bytes: bytes) -> list[Image.Image]:
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    background = Image.new("RGBA", image.size, "white")
    merged = Image.alpha_composite(background, image).convert("L")
    merged = ImageOps.autocontrast(merged)

    variants: list[Image.Image] = []
    for scale in (8, 12, 16):
        upscaled = merged.resize((max(merged.width * scale, 32), max(merged.height * scale, 32)))
        variants.append(upscaled)
        variants.append(upscaled.point(lambda p: 255 if p > 160 else 0))
        variants.append(upscaled.point(lambda p: 255 if p > 200 else 0))
        variants.append(upscaled.filter(ImageFilter.SHARPEN))
    return variants


def _collect_structure_marker_candidates(image_bytes: bytes) -> list[StructureOcrCandidate]:
    try:
        import pytesseract
    except Exception:  # noqa: BLE001
        return []

    try:
        grouped: dict[str, dict[str, float]] = {}
        for image in _prepare_structure_marker_variants(image_bytes):
            for psm in (6, 7, 8, 13):
                config = f"--psm {psm} -c tessedit_char_whitelist=0123456789."
                text = (pytesseract.image_to_string(image, config=config) or "").strip()
                text = text.replace(" ", "")
                text = re.sub(r"[^0-9.]", "", text)
                if not text:
                    continue
                data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
                confidences: list[float] = []
                for raw_conf in data.get("conf", []):
                    try:
                        conf = float(raw_conf)
                    except Exception:  # noqa: BLE001
                        continue
                    if conf >= 0:
                        confidences.append(conf)
                mean_conf = round(sum(confidences) / len(confidences), 2) if confidences else None
                current = grouped.setdefault(text, {"votes": 0.0, "confidence_total": 0.0, "confidence_count": 0.0})
                current["votes"] += 1
                if mean_conf is not None:
                    current["confidence_total"] += mean_conf
                    current["confidence_count"] += 1
        candidates: list[StructureOcrCandidate] = []
        for text, payload in grouped.items():
            confidence = None
            if payload["confidence_count"] > 0:
                confidence = round(payload["confidence_total"] / payload["confidence_count"], 2)
            candidates.append(
                StructureOcrCandidate(
                    text=text,
                    confidence=confidence,
                    votes=int(payload["votes"]),
                )
            )
        candidates.sort(key=lambda item: (-item.votes, -(item.confidence or -1.0), item.text))
        return candidates
    except Exception:  # noqa: BLE001
        return []


def _normalize_structure_marker_from_context(candidate: str, parent_heading_index: str | None) -> str | None:
    if not parent_heading_index:
        return None
    normalized = re.sub(r"[^0-9.]", "", candidate)
    if not normalized:
        return None
    compact = normalized.replace(".", "")
    parent_parts = parent_heading_index.split(".")
    candidate_prefixes = [".".join(parent_parts[:size]) for size in range(len(parent_parts), 1, -1)]
    for prefix in candidate_prefixes:
        prefix_compact = prefix.replace(".", "")
        if re.fullmatch(r"\d+(?:\.\d+)+", normalized):
            if normalized.startswith(f"{prefix}."):
                return normalized
            parts = normalized.split(".")
            if len(parts) == 2 and parts[0] == prefix_compact and parts[1].isdigit():
                return f"{prefix}.{parts[1]}"
        if compact.startswith(prefix_compact):
            suffix = compact[len(prefix_compact) :]
            if suffix and suffix.isdigit():
                return f"{prefix}.{suffix}"
    return None


def _expected_current_from_child(child_heading_index: str | None) -> str | None:
    if not child_heading_index or "." not in child_heading_index:
        return None
    current, _, suffix = child_heading_index.rpartition(".")
    if not current or not suffix.isdigit():
        return None
    return current


def _candidate_matches_expected(candidate: str, expected: str | None) -> bool:
    if not expected:
        return False
    compact_candidate = re.sub(r"[^0-9]", "", candidate)
    compact_expected = expected.replace(".", "")
    return bool(compact_candidate) and compact_candidate == compact_expected


def _interpolate_from_siblings(
    previous_recovered_text: str | None,
    next_recovered_text: str | None,
) -> str | None:
    if not previous_recovered_text or not next_recovered_text:
        return None
    previous_parts = previous_recovered_text.split(".")
    next_parts = next_recovered_text.split(".")
    if len(previous_parts) != len(next_parts) or len(previous_parts) < 2:
        return None
    if previous_parts[:-1] != next_parts[:-1]:
        return None
    try:
        previous_last = int(previous_parts[-1])
        next_last = int(next_parts[-1])
    except ValueError:
        return None
    if next_last - previous_last != 2:
        return None
    return ".".join(previous_parts[:-1] + [str(previous_last + 1)])


def _increment_sibling(previous_recovered_text: str | None) -> str | None:
    if not previous_recovered_text:
        return None
    parts = previous_recovered_text.split(".")
    if len(parts) < 2:
        return None
    try:
        last_value = int(parts[-1])
    except ValueError:
        return None
    return ".".join(parts[:-1] + [str(last_value + 1)])


def _resolve_structure_marker_recovery(
    candidates: list[StructureOcrCandidate],
    parent_heading_index: str | None,
    child_heading_index: str | None = None,
    previous_recovered_text: str | None = None,
    next_recovered_text: str | None = None,
) -> StructureRecoveryDecision:
    source_candidates = [
        {
            "text": candidate.text,
            "votes": candidate.votes,
            "confidence": candidate.confidence,
        }
        for candidate in candidates
    ]
    exact_candidates = [candidate for candidate in candidates if re.fullmatch(r"\d+(?:\.\d+)+", candidate.text)]
    exact_context_candidates: list[StructureOcrCandidate] = []
    if parent_heading_index or child_heading_index:
        for candidate in exact_candidates:
            parent_match = parent_heading_index is not None and candidate.text.startswith(f"{parent_heading_index}.")
            child_match = child_heading_index is not None and child_heading_index.startswith(f"{candidate.text}.")
            if parent_match or child_match:
                exact_context_candidates.append(candidate)
    if exact_context_candidates:
        best_exact = exact_context_candidates[0]
        competing = [
            candidate
            for candidate in exact_context_candidates[1:]
            if candidate.votes == best_exact.votes and (candidate.confidence or -1.0) == (best_exact.confidence or -1.0)
        ]
        if competing and any(candidate.text != best_exact.text for candidate in competing):
            return StructureRecoveryDecision(
                text=None,
                confidence=None,
                reason="STRUCTURE_MARKER_SUPPRESSED_AMBIGUOUS",
                recovery_strategy=None,
                context_validated=False,
                parent_heading_index=parent_heading_index,
                source_candidates=source_candidates,
            )
        return StructureRecoveryDecision(
            text=best_exact.text,
            confidence=best_exact.confidence,
            reason="STRUCTURE_MARKER_RECOVERED_EXACT",
            recovery_strategy="ocr_exact",
            context_validated=False,
            parent_heading_index=parent_heading_index,
            source_candidates=source_candidates,
        )

    expected_from_child = _expected_current_from_child(child_heading_index)
    if expected_from_child and any(_candidate_matches_expected(candidate.text, expected_from_child) for candidate in candidates):
        matching = [candidate for candidate in candidates if _candidate_matches_expected(candidate.text, expected_from_child)]
        best_match = sorted(matching, key=lambda item: (-item.votes, -(item.confidence or -1.0), item.text))[0]
        return StructureRecoveryDecision(
            text=expected_from_child,
            confidence=best_match.confidence,
            reason="STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED",
            recovery_strategy="child_heading_context",
            context_validated=True,
            parent_heading_index=parent_heading_index,
            source_candidates=source_candidates,
        )

    context_candidates: list[tuple[str, StructureOcrCandidate]] = []
    for candidate in candidates:
        normalized = _normalize_structure_marker_from_context(candidate.text, parent_heading_index)
        if normalized is not None:
            context_candidates.append((normalized, candidate))
    if context_candidates:
        grouped: dict[str, dict[str, float | str | None]] = {}
        for normalized, candidate in context_candidates:
            entry = grouped.setdefault(
                normalized,
                {
                    "votes": 0.0,
                    "confidence_total": 0.0,
                    "confidence_count": 0.0,
                },
            )
            entry["votes"] += candidate.votes
            if candidate.confidence is not None:
                entry["confidence_total"] += candidate.confidence
                entry["confidence_count"] += 1
        ranked = sorted(
            grouped.items(),
            key=lambda item: (
                -int(item[1]["votes"]),
                -(round(float(item[1]["confidence_total"]) / float(item[1]["confidence_count"]), 2) if item[1]["confidence_count"] else -1.0),
                item[0],
            ),
        )
        best_text, best_payload = ranked[0]
        if len(ranked) > 1 and ranked[1][1]["votes"] == best_payload["votes"] and ranked[1][0] != best_text:
            return StructureRecoveryDecision(
                text=None,
                confidence=None,
                reason="STRUCTURE_MARKER_SUPPRESSED_AMBIGUOUS",
                recovery_strategy=None,
                context_validated=False,
                parent_heading_index=parent_heading_index,
                source_candidates=source_candidates,
            )
        confidence = None
        if best_payload["confidence_count"]:
            confidence = round(float(best_payload["confidence_total"]) / float(best_payload["confidence_count"]), 2)
        return StructureRecoveryDecision(
            text=best_text,
            confidence=confidence,
            reason="STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED",
            recovery_strategy="parent_heading_context",
            context_validated=True,
            parent_heading_index=parent_heading_index,
            source_candidates=source_candidates,
        )

    expected_from_siblings = _interpolate_from_siblings(previous_recovered_text, next_recovered_text)
    if expected_from_siblings and any(_candidate_matches_expected(candidate.text, expected_from_siblings) for candidate in candidates):
        matching = [candidate for candidate in candidates if _candidate_matches_expected(candidate.text, expected_from_siblings)]
        best_match = sorted(matching, key=lambda item: (-item.votes, -(item.confidence or -1.0), item.text))[0]
        return StructureRecoveryDecision(
            text=expected_from_siblings,
            confidence=best_match.confidence,
            reason="STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED",
            recovery_strategy="sibling_sequence_context",
            context_validated=True,
            parent_heading_index=parent_heading_index,
            source_candidates=source_candidates,
        )

    expected_from_previous = _increment_sibling(previous_recovered_text)
    if expected_from_previous and any(_candidate_matches_expected(candidate.text, expected_from_previous) for candidate in candidates):
        matching = [candidate for candidate in candidates if _candidate_matches_expected(candidate.text, expected_from_previous)]
        best_match = sorted(matching, key=lambda item: (-item.votes, -(item.confidence or -1.0), item.text))[0]
        return StructureRecoveryDecision(
            text=expected_from_previous,
            confidence=best_match.confidence,
            reason="STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED",
            recovery_strategy="previous_sibling_context",
            context_validated=True,
            parent_heading_index=parent_heading_index,
            source_candidates=source_candidates,
        )

    strong_exact_candidates = [candidate for candidate in exact_candidates if candidate.text.count(".") >= 2]
    if strong_exact_candidates:
        best_exact = strong_exact_candidates[0]
        return StructureRecoveryDecision(
            text=best_exact.text,
            confidence=best_exact.confidence,
            reason="STRUCTURE_MARKER_RECOVERED_EXACT",
            recovery_strategy="ocr_exact",
            context_validated=False,
            parent_heading_index=parent_heading_index,
            source_candidates=source_candidates,
        )

    return StructureRecoveryDecision(
        text=None,
        confidence=None,
        reason="STRUCTURE_MARKER_SUPPRESSED_NO_CANDIDATE",
        recovery_strategy=None,
        context_validated=False,
        parent_heading_index=parent_heading_index,
        source_candidates=source_candidates,
    )


def _append_structure_marker_result(
    result: ImageExtractionResult,
    marker: PendingStructureMarker,
    recovery: StructureRecoveryDecision,
) -> None:
    result.excluded_assets.append(
        ExcludedImageAsset(
            page=marker.page,
            index=marker.index,
            reason=recovery.reason,
            classification="STRUCTURE_MARKER",
            recovered_text=recovery.text,
            recovered_confidence=recovery.confidence,
            ocr_candidates=recovery.source_candidates,
            recovery_strategy=recovery.recovery_strategy,
            context_validated=recovery.context_validated,
            parent_heading_index=recovery.parent_heading_index,
            bbox=marker.bbox,
            width=marker.width,
            height=marker.height,
            sha256=marker.sha256,
        )
    )
    if recovery.text:
        result.structure_recoveries.append(
            {
                "page": marker.page,
                "top": marker.title_top,
                "title_text": marker.title_text,
                "recovered_text": recovery.text,
                "confidence": recovery.confidence,
                "recovery_strategy": recovery.recovery_strategy,
                "context_validated": recovery.context_validated,
                "source_candidates": recovery.source_candidates,
                "parent_heading_index": recovery.parent_heading_index,
            }
        )


def _resolve_structure_markers(markers: list[PendingStructureMarker]) -> list[tuple[PendingStructureMarker, StructureRecoveryDecision]]:
    ordered = sorted(markers, key=lambda item: (item.page, item.top, item.index))
    strong_recoveries: list[StructureRecoveryDecision | None] = [None] * len(ordered)
    for idx, marker in enumerate(ordered):
        decision = _resolve_structure_marker_recovery(
            marker.ocr_candidates,
            marker.parent_heading_index,
            marker.child_heading_index,
        )
        if decision.text is not None:
            strong_recoveries[idx] = decision

    resolved: list[tuple[PendingStructureMarker, StructureRecoveryDecision]] = []
    for idx, marker in enumerate(ordered):
        previous_recovered = None
        next_recovered = None
        for back in range(idx - 1, -1, -1):
            if strong_recoveries[back] is not None and strong_recoveries[back].text is not None:
                previous_recovered = strong_recoveries[back].text
                break
        for forward in range(idx + 1, len(ordered)):
            if strong_recoveries[forward] is not None and strong_recoveries[forward].text is not None:
                next_recovered = strong_recoveries[forward].text
                break
        recovery = _resolve_structure_marker_recovery(
            marker.ocr_candidates,
            marker.parent_heading_index,
            marker.child_heading_index,
            previous_recovered_text=previous_recovered,
            next_recovered_text=next_recovered,
        )
        resolved.append((marker, recovery))
    return resolved


def _is_decorative(
    *,
    width: int | None,
    height: int | None,
    hash_count: int,
    caption_nearby: bool,
) -> tuple[bool, str | None]:
    small = (height is not None and height <= 10) or (width is not None and width <= 20)
    tiny = (height is not None and height <= 8) or (width is not None and width <= 16)
    if tiny and not caption_nearby:
        return True, "TINY_DECORATIVE"
    if small and hash_count >= 2 and not caption_nearby:
        return True, "REPEATED_SMALL_DECORATIVE"
    return False, None


def extract_images(
    reader: PdfReader,
    pdf_path: Path,
    selected_pages: list[int],
    password: str | None,
    output_dir: Path,
    image_mode: ImageMode,
) -> ImageExtractionResult:
    result = ImageExtractionResult()
    images_root = output_dir / "assets" / "images"
    images_root.mkdir(parents=True, exist_ok=True)

    page_image_boxes: dict[int, list[dict]] = {}
    page_text_lines: dict[int, list[dict]] = {}
    try:
        with pdfplumber.open(str(pdf_path), password=password) as pdf:
            for page_number in selected_pages:
                page = pdf.pages[page_number - 1]
                boxes = sorted(
                    (page.images or []),
                    key=lambda item: (float(item.get("top", 0.0)), float(item.get("x0", 0.0))),
                )
                page_image_boxes[page_number] = boxes
                page_text_lines[page_number] = page.extract_text_lines() or []
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(
            WarningEntry(
                code="IMAGE_POSITION_MAPPING_FAILED",
                message=f"Failed to read image positions from pdfplumber: {exc}",
            )
        )

    hashed_candidates: list[dict] = []
    for page_number in selected_pages:
        page = reader.pages[page_number - 1]
        logger.debug("Extracting images for page=%s", page_number)
        try:
            raw_images = list(page.images)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(
                WarningEntry(
                    code="IMAGE_EXTRACTION_FAILED",
                    message=f"Failed to read image objects: {exc}",
                    page=page_number,
                )
            )
            continue
        for index, image in enumerate(raw_images, start=1):
            try:
                image_bytes = image.data
                sha256 = hashlib.sha256(image_bytes).hexdigest()
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(
                    WarningEntry(
                        code="IMAGE_EXTRACTION_FAILED",
                        message=f"Failed to decode image bytes: {exc}",
                        page=page_number,
                        details={"image_index": index},
                    )
                )
                continue
            width, height = _image_dimensions(image)
            hashed_candidates.append(
                {
                    "page": page_number,
                    "index": index,
                    "image": image,
                    "bytes": image_bytes,
                    "sha256": sha256,
                    "width": width,
                    "height": height,
                }
            )

    hash_counter = Counter(item["sha256"] for item in hashed_candidates)
    pending_structure_markers: dict[int, list[PendingStructureMarker]] = {}

    for candidate in hashed_candidates:
        page_number = int(candidate["page"])
        index = int(candidate["index"])
        image = candidate["image"]
        image_bytes = candidate["bytes"]
        sha256 = candidate["sha256"]
        width = candidate["width"]
        height = candidate["height"]

        extension = _guess_extension(getattr(image, "name", ""))
        filename = f"page-{page_number:04d}-figure-{index:03d}.{extension}"
        rel_path = f"assets/images/{filename}"
        disk_path = images_root / filename

        bbox_payload = None
        top = float(index) * 1000.0
        bottom = top
        mapped = page_image_boxes.get(page_number, [])
        if len(mapped) >= index:
            box = mapped[index - 1]
            x0 = float(box.get("x0", 0.0))
            y0 = float(box.get("top", 0.0))
            x1 = float(box.get("x1", 0.0))
            y1 = float(box.get("bottom", 0.0))
            top = y0
            bottom = y1
            bbox_payload = [x0, y0, x1, y1]
            if width is None and box.get("width") is not None:
                width = int(float(box["width"]))
            if height is None and box.get("height") is not None:
                height = int(float(box["height"]))

        caption_nearby = _is_caption_nearby(page_text_lines.get(page_number, []), top, bottom)
        caption_text = _extract_caption_text(page_text_lines.get(page_number, []), top, bottom) if caption_nearby else None
        title_line = _find_structure_title(page_text_lines.get(page_number, []), bbox_payload)
        if _is_structure_marker_candidate(
            bbox=bbox_payload,
            width=width,
            height=height,
            title_line=title_line,
        ):
            parent_heading_index = _find_parent_heading_index(page_text_lines.get(page_number, []), title_line)
            child_heading_index = _find_child_heading_index(page_text_lines, page_number, title_line)
            ocr_candidates = _collect_structure_marker_candidates(image_bytes)
            pending_structure_markers.setdefault(page_number, []).append(
                PendingStructureMarker(
                    page=page_number,
                    index=index,
                    top=top,
                    bbox=bbox_payload,
                    width=width,
                    height=height,
                    sha256=sha256,
                    title_text=str(title_line.get("text", "")).strip() if title_line is not None else "",
                    title_top=float(title_line.get("top", top)) if title_line is not None else top,
                    parent_heading_index=parent_heading_index,
                    child_heading_index=child_heading_index,
                    ocr_candidates=ocr_candidates,
                )
            )
            continue
        is_decorative, reason = _is_decorative(
            width=width,
            height=height,
            hash_count=hash_counter.get(sha256, 1),
            caption_nearby=caption_nearby,
        )
        if is_decorative:
            result.excluded_assets.append(
                ExcludedImageAsset(
                    page=page_number,
                    index=index,
                    reason=reason or "DECORATIVE",
                    bbox=bbox_payload,
                    width=width,
                    height=height,
                    sha256=sha256,
                )
            )
            continue

        try:
            alt_text = f"Image page-{page_number:04d}-figure-{index:03d}"
            if image_mode == ImageMode.REFERENCED:
                disk_path.write_bytes(image_bytes)
            markdown = _build_markdown(
                mode=image_mode,
                alt_text=alt_text,
                rel_path=rel_path,
                extension=extension,
                data=image_bytes,
                page=page_number,
                index=index,
            )
            page_blocks = result.blocks_by_page.setdefault(page_number, [])
            page_blocks.append(
                ImageBlock(
                    page=page_number,
                    index=index,
                    markdown=markdown,
                    top=top,
                    anchor_line_index=0,
                    bbox=tuple(bbox_payload) if bbox_payload else None,
                )
            )
            result.assets.append(
                ImageAsset(
                    page=page_number,
                    index=index,
                    path=rel_path,
                    alt_text=alt_text,
                    caption_text=caption_text,
                    caption_source="nearby_caption" if caption_text else None,
                    bbox=bbox_payload,
                    width=width,
                    height=height,
                    sha256=sha256,
                )
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(
                WarningEntry(
                    code="IMAGE_EXTRACTION_FAILED",
                    message=f"Failed to process image object: {exc}",
                    page=page_number,
                    details={"image_index": index},
                )
            )

    all_pending_markers = [
        marker
        for page_number in sorted(pending_structure_markers)
        for marker in pending_structure_markers[page_number]
    ]
    for marker, recovery in _resolve_structure_markers(all_pending_markers):
        _append_structure_marker_result(result, marker, recovery)

    return result
