from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from pdf2md.models import ImageAsset, ImageMode, WarningEntry


@dataclass
class ImageBlock:
    page: int
    index: int
    markdown: str
    top: float


@dataclass
class ImageExtractionResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    assets: list[ImageAsset] = field(default_factory=list)
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
    try:
        with pdfplumber.open(str(pdf_path), password=password) as pdf:
            for page_number in selected_pages:
                page = pdf.pages[page_number - 1]
                boxes = sorted(
                    (page.images or []),
                    key=lambda item: (float(item.get("top", 0.0)), float(item.get("x0", 0.0))),
                )
                page_image_boxes[page_number] = boxes
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(
            WarningEntry(
                code="IMAGE_POSITION_MAPPING_FAILED",
                message=f"Failed to read image positions from pdfplumber: {exc}",
            )
        )

    for page_number in selected_pages:
        page = reader.pages[page_number - 1]
        page_blocks: list[ImageBlock] = []

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
                extension = _guess_extension(getattr(image, "name", ""))
                filename = f"page-{page_number:04d}-figure-{index:03d}.{extension}"
                disk_path = images_root / filename
                rel_path = f"assets/images/{filename}"
                image_bytes = image.data
                disk_path.write_bytes(image_bytes)
                sha256 = hashlib.sha256(image_bytes).hexdigest()
                alt_text = f"Image page-{page_number:04d}-figure-{index:03d}"
                bbox_payload = None
                width = None
                height = None
                top = float(index) * 1000.0
                mapped = page_image_boxes.get(page_number, [])
                if len(mapped) >= index:
                    box = mapped[index - 1]
                    x0 = float(box.get("x0", 0.0))
                    y0 = float(box.get("top", 0.0))
                    x1 = float(box.get("x1", 0.0))
                    y1 = float(box.get("bottom", 0.0))
                    top = y0
                    bbox_payload = [x0, y0, x1, y1]
                    if box.get("width") is not None:
                        width = int(float(box["width"]))
                    if box.get("height") is not None:
                        height = int(float(box["height"]))

                page_blocks.append(
                    ImageBlock(
                        page=page_number,
                        index=index,
                        markdown=_build_markdown(
                            mode=image_mode,
                            alt_text=alt_text,
                            rel_path=rel_path,
                            extension=extension,
                            data=image_bytes,
                            page=page_number,
                            index=index,
                        ),
                        top=top,
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
        if page_blocks:
            result.blocks_by_page[page_number] = page_blocks

    return result
