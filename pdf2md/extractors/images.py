from __future__ import annotations

import base64
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from pdf2md.models import ExcludedImageAsset, ImageAsset, ImageMode, WarningEntry

CAPTION_PATTERN = re.compile(r"\b(figure|fig\.?|chart|도표|그림)\b", re.IGNORECASE)


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
            if CAPTION_PATTERN.search(text):
                return True
    return False


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
            disk_path.write_bytes(image_bytes)
            alt_text = f"Image page-{page_number:04d}-figure-{index:03d}"
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

    return result
