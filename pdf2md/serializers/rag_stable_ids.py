from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


def normalize_seed_text(text: str) -> str:
    """Normalize text only for deterministic metadata hashing."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def stable_text_hash(text: str) -> str:
    """Return the deterministic SHA-1 hash of normalized source text."""
    return hashlib.sha1(normalize_seed_text(text).encode("utf-8")).hexdigest()


def source_dedupe_key(source_refs: list[dict[str, Any]]) -> str | None:
    """Build the stable duplicate key used by RAG sidecars."""
    dedupe_key = "|".join(
        sorted(str(ref.get("source_id")) for ref in source_refs if isinstance(ref, dict) and ref.get("source_id"))
    )
    return dedupe_key or None


def section_path_from_record(record: dict[str, Any]) -> str:
    """Return the canonical section path string for stable-id inputs."""
    section_path = str(record.get("section_path") or "").strip()
    if section_path:
        return section_path
    heading_path = record.get("heading_path")
    if isinstance(heading_path, list):
        return " > ".join(str(item) for item in heading_path if str(item).strip())
    return ""


def page_range_from_record(record: dict[str, Any]) -> list[int]:
    """Return a two-item page range using page as a fallback."""
    page_range = record.get("page_range")
    if isinstance(page_range, list) and len(page_range) == 2:
        try:
            return [int(page_range[0]), int(page_range[1])]
        except (TypeError, ValueError):
            pass
    try:
        page = int(record.get("page") or 0)
    except (TypeError, ValueError):
        page = 0
    return [page, page]


def primary_source_ref(source_refs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the original source locator before sidecar ordinal refs."""
    for ref in source_refs:
        if isinstance(ref, dict) and ref.get("source_type") and ref.get("source_id"):
            return ref
    for ref in source_refs:
        if isinstance(ref, dict):
            return ref
    return None


def stable_source_id(
    *,
    source_sha256: str,
    page_range: list[int],
    section_path: str,
    source_type: str,
    source_id: str,
    text: str,
) -> str:
    """Return a deterministic source node id seed."""
    payload = [
        source_sha256,
        json.dumps(page_range, separators=(",", ":")),
        section_path,
        source_type,
        source_id,
        stable_text_hash(text),
    ]
    return hashlib.sha1("\x1f".join(payload).encode("utf-8")).hexdigest()


def stable_requirement_seed(
    *,
    source_sha256: str,
    section_path: str,
    locator_id: str,
    text: str,
) -> str:
    """Return a deterministic downstream requirement seed."""
    payload = [source_sha256, section_path, locator_id, normalize_seed_text(text)]
    return hashlib.sha1("\x1f".join(payload).encode("utf-8")).hexdigest()


def with_stable_source_metadata(
    record: dict[str, Any],
    *,
    source_sha256: str,
    text: str | None = None,
    source_refs: list[dict[str, Any]] | None = None,
    requirement_locator_id: str | None = None,
) -> dict[str, Any]:
    """Return a record copy with stable source and requirement seed metadata."""
    if not source_sha256:
        return dict(record)
    updated = dict(record)
    record_text = normalize_seed_text(text if text is not None else str(record.get("text") or ""))
    refs = source_refs if source_refs is not None else list(record.get("source_refs") or [])
    if refs and not updated.get("source_dedupe_key"):
        updated["source_dedupe_key"] = source_dedupe_key(refs)
    if record_text:
        updated["source_sha256"] = source_sha256
        page_range = page_range_from_record(updated)
        section_path = section_path_from_record(updated)
        ref = primary_source_ref(refs)
        source_type = str(ref.get("source_type") or "") if ref else ""
        source_id = str(ref.get("source_id") or "") if ref else ""
        if source_type and source_id:
            updated["stable_source_id"] = stable_source_id(
                source_sha256=source_sha256,
                page_range=page_range,
                section_path=section_path,
                source_type=source_type,
                source_id=source_id,
                text=record_text,
            )
        locator_id = requirement_locator_id or str(
            updated.get("table_row_id")
            or updated.get("domain_unit_id")
            or updated.get("technical_table_unit_id")
            or source_id
        )
        if locator_id:
            updated["stable_requirement_seed"] = stable_requirement_seed(
                source_sha256=source_sha256,
                section_path=section_path,
                locator_id=locator_id,
                text=record_text,
            )
    return updated
