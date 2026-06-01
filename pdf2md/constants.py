from __future__ import annotations

from dataclasses import dataclass


class WarningCode:
    PDF_OPEN_FAILED = "PDF_OPEN_FAILED"
    INVALID_PAGE_RANGE = "INVALID_PAGE_RANGE"
    TEXT_EXTRACTION_FAILED = "TEXT_EXTRACTION_FAILED"
    OCR_RUNTIME_UNAVAILABLE = "OCR_RUNTIME_UNAVAILABLE"
    OCR_FAILED = "OCR_FAILED"
    OCR_CONFIDENCE_CRITICAL = "OCR_CONFIDENCE_CRITICAL"
    OCR_CONFIDENCE_WARN = "OCR_CONFIDENCE_WARN"
    OCR_EMPTY_RESULT = "OCR_EMPTY_RESULT"
    IMAGE_POSITION_MAPPING_FAILED = "IMAGE_POSITION_MAPPING_FAILED"
    IMAGE_EXTRACTION_FAILED = "IMAGE_EXTRACTION_FAILED"
    IMAGE_CROP_REJECTED = "IMAGE_CROP_REJECTED"
    TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING = "TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING"
    TABLE_GFM_UNSAFE_FALLBACK_HTML = "TABLE_GFM_UNSAFE_FALLBACK_HTML"
    TABLE_COMPLEXITY_HTML_FALLBACK = "TABLE_COMPLEXITY_HTML_FALLBACK"
    TABLE_COMPLEXITY_MARKDOWN_COERCED = "TABLE_COMPLEXITY_MARKDOWN_COERCED"
    TABLE_EXTRACTION_FAILED = "TABLE_EXTRACTION_FAILED"


class WarningDomain:
    PDF = "pdf"
    PAGE = "page"
    TEXT = "text"
    OCR = "ocr"
    IMAGE = "image"
    TABLE = "table"
    TECHNICAL_PROFILE = "technical_profile"
    UNKNOWN = "unknown"


class WarningSeverity:
    ACTIONABLE = "actionable"
    ADVISORY = "advisory"


@dataclass(frozen=True)
class WarningCodeSpec:
    code: str
    domain: str
    default_severity: str = WarningSeverity.ACTIONABLE
    affects_exit_code: bool = True


WARNING_CODE_REGISTRY: dict[str, WarningCodeSpec] = {
    WarningCode.PDF_OPEN_FAILED: WarningCodeSpec(WarningCode.PDF_OPEN_FAILED, WarningDomain.PDF),
    WarningCode.INVALID_PAGE_RANGE: WarningCodeSpec(WarningCode.INVALID_PAGE_RANGE, WarningDomain.PAGE),
    WarningCode.TEXT_EXTRACTION_FAILED: WarningCodeSpec(WarningCode.TEXT_EXTRACTION_FAILED, WarningDomain.TEXT),
    WarningCode.OCR_RUNTIME_UNAVAILABLE: WarningCodeSpec(WarningCode.OCR_RUNTIME_UNAVAILABLE, WarningDomain.OCR),
    WarningCode.OCR_FAILED: WarningCodeSpec(WarningCode.OCR_FAILED, WarningDomain.OCR),
    WarningCode.OCR_CONFIDENCE_CRITICAL: WarningCodeSpec(WarningCode.OCR_CONFIDENCE_CRITICAL, WarningDomain.OCR),
    WarningCode.OCR_CONFIDENCE_WARN: WarningCodeSpec(WarningCode.OCR_CONFIDENCE_WARN, WarningDomain.OCR),
    WarningCode.OCR_EMPTY_RESULT: WarningCodeSpec(WarningCode.OCR_EMPTY_RESULT, WarningDomain.OCR),
    WarningCode.IMAGE_POSITION_MAPPING_FAILED: WarningCodeSpec(
        WarningCode.IMAGE_POSITION_MAPPING_FAILED,
        WarningDomain.IMAGE,
    ),
    WarningCode.IMAGE_EXTRACTION_FAILED: WarningCodeSpec(WarningCode.IMAGE_EXTRACTION_FAILED, WarningDomain.IMAGE),
    WarningCode.IMAGE_CROP_REJECTED: WarningCodeSpec(WarningCode.IMAGE_CROP_REJECTED, WarningDomain.IMAGE),
    WarningCode.TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING: WarningCodeSpec(
        WarningCode.TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING,
        WarningDomain.TECHNICAL_PROFILE,
        default_severity=WarningSeverity.ADVISORY,
        affects_exit_code=False,
    ),
    WarningCode.TABLE_GFM_UNSAFE_FALLBACK_HTML: WarningCodeSpec(
        WarningCode.TABLE_GFM_UNSAFE_FALLBACK_HTML,
        WarningDomain.TABLE,
    ),
    WarningCode.TABLE_COMPLEXITY_HTML_FALLBACK: WarningCodeSpec(
        WarningCode.TABLE_COMPLEXITY_HTML_FALLBACK,
        WarningDomain.TABLE,
        default_severity=WarningSeverity.ADVISORY,
        affects_exit_code=False,
    ),
    WarningCode.TABLE_COMPLEXITY_MARKDOWN_COERCED: WarningCodeSpec(
        WarningCode.TABLE_COMPLEXITY_MARKDOWN_COERCED,
        WarningDomain.TABLE,
    ),
    WarningCode.TABLE_EXTRACTION_FAILED: WarningCodeSpec(WarningCode.TABLE_EXTRACTION_FAILED, WarningDomain.TABLE),
}


def warning_code_spec(code: str) -> WarningCodeSpec:
    """Return warning metadata, defaulting unknown codes to actionable non-domain warnings."""
    return WARNING_CODE_REGISTRY.get(code, WarningCodeSpec(code=code, domain=WarningDomain.UNKNOWN))


class StructureRecoveryReason:
    RECOVERED_EXACT = "STRUCTURE_MARKER_RECOVERED_EXACT"
    RECOVERED_CONTEXT_VALIDATED = "STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED"
    SUPPRESSED_NO_CANDIDATE = "STRUCTURE_MARKER_SUPPRESSED_NO_CANDIDATE"
    SUPPRESSED_AMBIGUOUS = "STRUCTURE_MARKER_SUPPRESSED_AMBIGUOUS"


class StructureRecoveryStrategy:
    OCR_EXACT = "ocr_exact"
    CHILD_HEADING_CONTEXT = "child_heading_context"
    PARENT_HEADING_CONTEXT = "parent_heading_context"
    SIBLING_SEQUENCE_CONTEXT = "sibling_sequence_context"
    PREVIOUS_SIBLING_CONTEXT = "previous_sibling_context"


class ImageExcludeReason:
    TINY_DECORATIVE = "TINY_DECORATIVE"
    REPEATED_SMALL_DECORATIVE = "REPEATED_SMALL_DECORATIVE"
    DECORATIVE = "DECORATIVE"


class ImageClassification:
    STRUCTURE_MARKER = "STRUCTURE_MARKER"


class TableReason:
    AMBIGUOUS_GRID = "AMBIGUOUS_GRID"
    SPARSE_LAYOUT = "SPARSE_LAYOUT"
    HEADER_FRAGMENTED = "HEADER_FRAGMENTED"
    LOW_DATA_DENSITY = "LOW_DATA_DENSITY"
    MULTILINE_CELL = "MULTILINE_CELL"
    LONG_CELL = "LONG_CELL"
    OVERWIDE_TABLE = "OVERWIDE_TABLE"
    TOO_FEW_COLUMNS = "TOO_FEW_COLUMNS"
    TOO_FEW_ROWS = "TOO_FEW_ROWS"
    MULTI_ROW_HEADER = "MULTI_ROW_HEADER"
    STUB_COLUMN = "STUB_COLUMN"
    FOOTNOTE_ROW = "FOOTNOTE_ROW"
    MERGED_CELL_SUSPECTED = "MERGED_CELL_SUSPECTED"
    LOW_HEADER_CONFIDENCE = "LOW_HEADER_CONFIDENCE"


class TableModeEmission:
    HTML = "html"
    GFM = "gfm"
    MARKDOWN = "markdown"


class TableDecisionReason:
    BLOCK_OVERLAP_SUPPRESSION = "BLOCK_OVERLAP_SUPPRESSION"
    NEAR_DUPLICATE_CAPTION = "NEAR_DUPLICATE_CAPTION"
    TEXT_FRAGMENT_SUPPRESSION = "TEXT_FRAGMENT_SUPPRESSION"


class TextSuppressionReason:
    REPEATED_HEADER_FOOTER = "REPEATED_HEADER_FOOTER"
