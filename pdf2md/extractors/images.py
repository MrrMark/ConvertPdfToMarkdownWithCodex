from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from pdf2md.models import ImageAsset, ImageMode, WarningEntry


@dataclass
class ImageBlock:
    page: int
    index: int
    markdown: str


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
    selected_pages: list[int],
    output_dir: Path,
    image_mode: ImageMode,
) -> ImageExtractionResult:
    result = ImageExtractionResult()
    images_root = output_dir / "assets" / "images"
    images_root.mkdir(parents=True, exist_ok=True)

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
                    )
                )
                result.assets.append(
                    ImageAsset(
                        page=page_number,
                        index=index,
                        path=rel_path,
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

    if image_mode == ImageMode.REFERENCED and not result.assets:
        result.warnings.append(
            WarningEntry(
                code="IMAGE_NOT_FOUND",
                message="No embedded images were found for selected pages.",
            )
        )

    return result
