from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path

from pdf2md.extractors.ocr_backends.base import OCRBackendMetadata, OCRBackendResult


class TesseractCliOCRBackend:
    """System tesseract executable adapter that does not require pytesseract."""

    metadata = OCRBackendMetadata(
        name="tesseract-cli",
        raw_confidence_unit="0_to_100",
        normalized_confidence_unit="0_to_1",
        higher_is_better=True,
        supports_languages=True,
    )

    def __init__(self) -> None:
        self._executable: str | None = None

    def is_available(self) -> bool:
        return _resolve_tesseract_cmd() is not None

    def configure_runtime(self) -> str | None:
        executable = _resolve_tesseract_cmd()
        if executable is None:
            return "tesseract_unavailable"
        self._executable = executable
        return None

    def recognize(self, image: object, *, lang: str) -> OCRBackendResult:
        executable = self._executable or _resolve_tesseract_cmd()
        if executable is None:
            raise RuntimeError("tesseract executable is unavailable")
        with tempfile.TemporaryDirectory(prefix="pdf2md-ocr-") as tmpdir:
            image_path = Path(tmpdir) / "region.png"
            save = getattr(image, "save", None)
            if save is None:
                raise RuntimeError("tesseract-cli backend requires a PIL-like image with save()")
            save(image_path)
            text = _run_tesseract(executable, image_path, lang=lang, output_format=None).strip()
            tsv = _run_tesseract(executable, image_path, lang=lang, output_format="tsv")
        return OCRBackendResult(text=text, confidence_data=_parse_tesseract_tsv(tsv))


def _resolve_tesseract_cmd() -> str | None:
    executable = shutil.which("tesseract")
    if executable:
        return executable
    homebrew_tesseract = Path("/opt/homebrew/bin/tesseract")
    if homebrew_tesseract.exists():
        return str(homebrew_tesseract)
    return None


def _run_tesseract(executable: str, image_path: Path, *, lang: str, output_format: str | None) -> str:
    command = [executable, str(image_path), "stdout", "-l", lang]
    if output_format is not None:
        command.append(output_format)
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"tesseract exited with {completed.returncode}")
    return completed.stdout


def _parse_tesseract_tsv(payload: str) -> dict[str, list[str]]:
    rows = csv.DictReader(payload.splitlines(), delimiter="\t")
    texts: list[str] = []
    confidences: list[str] = []
    for row in rows:
        text = (row.get("text") or "").strip()
        conf = (row.get("conf") or "").strip()
        if not text:
            continue
        texts.append(text)
        confidences.append(conf)
    return {"text": texts, "conf": confidences}
