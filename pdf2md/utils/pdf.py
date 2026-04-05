from __future__ import annotations

from pathlib import Path
from typing import Optional

from pypdf import PdfReader


class PdfOpenError(RuntimeError):
    pass


def open_pdf_reader(pdf_path: Path, password: Optional[str]) -> PdfReader:
    """Open PDF with optional password and return a ready-to-read reader."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        raise PdfOpenError(f"Unable to open PDF: {exc}") from exc

    if reader.is_encrypted:
        if not password:
            raise PdfOpenError("PDF is encrypted but no password was provided")
        result = reader.decrypt(password)
        if result == 0:
            raise PdfOpenError("Failed to decrypt PDF with the given password")

    return reader
