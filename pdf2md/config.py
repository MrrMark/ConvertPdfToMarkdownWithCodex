from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pdf2md.extractors.ocr_backends import supported_ocr_backends
from pdf2md.models import DomainAdapterMode, ImageMode, OutputProfile, RagSidecarScope, RagTableOutputMode, TableMode
from pdf2md.rag_profiles import DEFAULT_RAG_PURPOSE_PROFILE, SUPPORTED_RAG_PURPOSE_PROFILES
from pdf2md.utils.page_range import parse_page_range

SUPPORTED_RETRIEVAL_TOKENIZERS = ("char", "regex", "tiktoken-cl100k")
SUPPORTED_FIGURE_DESCRIPTION_BACKENDS = ("local-vlm", "docling")
SUPPORTED_OCR_BACKENDS = supported_ocr_backends()


class Config(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    input_pdf: Path
    output_dir: Path
    pages: Optional[str] = None
    password: Optional[str] = None
    image_mode: ImageMode = ImageMode.REFERENCED
    table_mode: TableMode = TableMode.AUTO
    rag_table_output: RagTableOutputMode = RagTableOutputMode.NONE
    output_profile: OutputProfile = OutputProfile.FULL
    rag_sidecar_scope: RagSidecarScope | None = None
    rag_profile: str = DEFAULT_RAG_PURPOSE_PROFILE
    domain_adapter: DomainAdapterMode = DomainAdapterMode.NONE
    manual_domain_adapter_label: Optional[str] = None
    manual_domain_adapter_keywords: Optional[str] = None
    confidential_safe_mode: bool = False
    force_ocr: bool = False
    ocr_lang: str = "eng"
    ocr_backend: str = "tesseract"
    keep_page_markers: bool = False
    remove_header_footer: bool = False
    dedupe_images: bool = False
    repair_hyphenation: bool = False
    figure_crop_fallback: bool = False
    retrieval_chunk_max_tokens: int = 512
    retrieval_tokenizer: str = "char"
    rag_contextual_embedding_text: bool = False
    rag_merge_sibling_text_chunks: bool = False
    rag_chunk_relationship_metadata: bool = False
    rag_figure_text_chunks: bool = False
    figure_region_ocr: bool = False
    rag_generated_figure_descriptions: bool = False
    figure_description_backend: str = "local-vlm"
    figure_structure_extraction: bool = False
    debug: bool = False
    verbose: bool = False
    skip_existing: bool = False
    page_workers: int = 1
    version: str = Field(default="0.1.0")
    markdown_filename: str = "document.md"
    manifest_filename: str = "manifest.json"
    report_filename: str = "report.json"
    rag_tables_markdown_filename: str = "rag_tables.md"
    rag_tables_jsonl_filename: str = "tables_rag.jsonl"
    rag_text_blocks_jsonl_filename: str = "text_blocks_rag.jsonl"
    semantic_units_jsonl_filename: str = "semantic_units_rag.jsonl"
    requirements_jsonl_filename: str = "requirements_rag.jsonl"
    cross_refs_jsonl_filename: str = "cross_refs_rag.jsonl"
    retrieval_chunks_jsonl_filename: str = "retrieval_chunks_rag.jsonl"
    figures_rag_jsonl_filename: str = "figures_rag.jsonl"
    figure_descriptions_jsonl_filename: str = "figure_descriptions_rag.jsonl"
    figure_structures_jsonl_filename: str = "figure_structures_rag.jsonl"
    domain_units_jsonl_filename: str = "domain_units_rag.jsonl"
    requirement_traceability_jsonl_filename: str = "requirement_traceability_rag.jsonl"
    technical_tables_jsonl_filename: str = "technical_tables_rag.jsonl"
    sanitized_report_filename: str = "sanitized_report.json"
    assets_dirname: str = "assets"

    def selected_pages(self, total_pages: int) -> list[int]:
        return parse_page_range(self.pages, total_pages)

    @field_validator("page_workers")
    @classmethod
    def _validate_page_workers(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page_workers must be >= 1")
        return value

    @field_validator("retrieval_chunk_max_tokens")
    @classmethod
    def _validate_retrieval_chunk_max_tokens(cls, value: int) -> int:
        if value < 1:
            raise ValueError("retrieval_chunk_max_tokens must be >= 1")
        return value

    @field_validator("retrieval_tokenizer")
    @classmethod
    def _validate_retrieval_tokenizer(cls, value: str) -> str:
        if value not in SUPPORTED_RETRIEVAL_TOKENIZERS:
            raise ValueError(f"retrieval_tokenizer must be one of: {', '.join(SUPPORTED_RETRIEVAL_TOKENIZERS)}")
        return value

    @field_validator("figure_description_backend")
    @classmethod
    def _validate_figure_description_backend(cls, value: str) -> str:
        if value not in SUPPORTED_FIGURE_DESCRIPTION_BACKENDS:
            raise ValueError(
                f"figure_description_backend must be one of: {', '.join(SUPPORTED_FIGURE_DESCRIPTION_BACKENDS)}"
            )
        return value

    @field_validator("ocr_backend")
    @classmethod
    def _validate_ocr_backend(cls, value: str) -> str:
        if value not in SUPPORTED_OCR_BACKENDS:
            raise ValueError(f"ocr_backend must be one of: {', '.join(SUPPORTED_OCR_BACKENDS)}")
        return value

    @field_validator("rag_profile")
    @classmethod
    def _validate_rag_profile(cls, value: str) -> str:
        if value not in SUPPORTED_RAG_PURPOSE_PROFILES:
            raise ValueError(f"rag_profile must be one of: {', '.join(SUPPORTED_RAG_PURPOSE_PROFILES)}")
        return value

    @field_validator("manual_domain_adapter_label", "manual_domain_adapter_keywords")
    @classmethod
    def _normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


def default_output_dir_for_input(input_pdf: Path) -> Path:
    """Return the default single-file output directory for an input PDF."""
    return input_pdf.parent / f"{input_pdf.stem}_output"
