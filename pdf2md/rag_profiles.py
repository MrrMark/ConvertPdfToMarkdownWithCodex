from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode


RagPurposeProfile = Literal[
    "preserve",
    "rag_optimized",
    "technical_spec_rag",
    "confidential_rag",
    "preserve_with_sidecars",
]
DEFAULT_RAG_PURPOSE_PROFILE: RagPurposeProfile = "preserve"
SUPPORTED_RAG_PURPOSE_PROFILES: tuple[RagPurposeProfile, ...] = (
    "preserve",
    "rag_optimized",
    "technical_spec_rag",
    "confidential_rag",
    "preserve_with_sidecars",
)


@dataclass(frozen=True)
class RagProfileOptions:
    """Reusable local-only option matrix for RAG-oriented conversion profiles."""

    image_mode: str = ImageMode.REFERENCED.value
    table_mode: str = TableMode.AUTO.value
    rag_table_output: str = RagTableOutputMode.NONE.value
    domain_adapter: str = DomainAdapterMode.NONE.value
    confidential_safe_mode: bool = False
    force_ocr: bool = False
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


def normalize_rag_profile(value: str | None) -> RagPurposeProfile:
    """Return a supported purpose profile, defaulting to conservative preservation."""
    if value in SUPPORTED_RAG_PURPOSE_PROFILES:
        return value
    return DEFAULT_RAG_PURPOSE_PROFILE


def rag_profile_options(profile: RagPurposeProfile | str | None) -> RagProfileOptions:
    """Return the deterministic option matrix for a purpose-specific RAG profile."""
    normalized = normalize_rag_profile(str(profile) if profile is not None else None)
    if normalized == "rag_optimized":
        return RagProfileOptions(
            rag_table_output=RagTableOutputMode.BOTH.value,
            keep_page_markers=True,
            remove_header_footer=True,
            repair_hyphenation=True,
            retrieval_tokenizer="regex",
            rag_contextual_embedding_text=True,
            rag_merge_sibling_text_chunks=True,
            rag_chunk_relationship_metadata=True,
        )
    if normalized == "technical_spec_rag":
        return RagProfileOptions(
            rag_table_output=RagTableOutputMode.BOTH.value,
            keep_page_markers=True,
            remove_header_footer=True,
            repair_hyphenation=True,
            retrieval_tokenizer="regex",
            rag_contextual_embedding_text=True,
            rag_merge_sibling_text_chunks=True,
            rag_chunk_relationship_metadata=True,
        )
    if normalized == "confidential_rag":
        return RagProfileOptions(
            rag_table_output=RagTableOutputMode.JSONL.value,
            confidential_safe_mode=True,
            remove_header_footer=True,
            repair_hyphenation=True,
            retrieval_tokenizer="regex",
            rag_contextual_embedding_text=True,
            rag_merge_sibling_text_chunks=True,
            rag_chunk_relationship_metadata=True,
        )
    if normalized == "preserve_with_sidecars":
        return RagProfileOptions(
            rag_table_output=RagTableOutputMode.JSONL.value,
            rag_chunk_relationship_metadata=True,
        )
    return RagProfileOptions()
