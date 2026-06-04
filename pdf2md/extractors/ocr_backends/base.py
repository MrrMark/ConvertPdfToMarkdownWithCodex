from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class OCRBackendMetadata:
    """Stable metadata describing an OCR backend confidence contract."""

    name: str
    raw_confidence_unit: str
    normalized_confidence_unit: str = "0_to_1"
    higher_is_better: bool = True
    supports_languages: bool = True


@dataclass(frozen=True)
class OCRBackendResult:
    """Raw OCR text and confidence payload from one rendered page image."""

    text: str
    confidence_data: dict[str, Any] = field(default_factory=dict)


class OCRBackend(Protocol):
    """Protocol for OCR engines used by the page OCR pipeline."""

    metadata: OCRBackendMetadata

    def is_available(self) -> bool:
        """Return true when required Python and executable dependencies are present."""

    def configure_runtime(self) -> str | None:
        """Prepare runtime command paths and return a missing-dependency reason, if any."""

    def recognize(self, image: object, *, lang: str) -> OCRBackendResult:
        """Run OCR for a rendered page image without correcting or rewriting text."""
