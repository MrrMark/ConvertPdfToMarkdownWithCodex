from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from pdf2md.config import Config, SUPPORTED_OCR_BACKENDS, default_output_dir_for_input
from pdf2md.models import (
    DomainAdapterMode,
    ImageMode,
    OutputProfile,
    RagSidecarScope,
    RagTableOutputMode,
    TableMode,
)
from pdf2md.pipeline import ConversionResult, run_conversion
from pdf2md.rag_profiles import SUPPORTED_RAG_PURPOSE_PROFILES, TECHNICAL_SPEC_RAG_PROFILES, rag_profile_options
from pdf2md.utils.page_range import parse_page_range
from pdf2md.utils.pdf import open_pdf_reader


SERVER_NAME = "pdf2md"
MCP_EXTRA = "pdf2md[mcp]"
MCP_ROOTS_ENV = "PDF2MD_MCP_ROOTS"
DEFAULT_WARNING_LIMIT = 20
WINDOW_OUTPUT_ROOT = "windows"
PAGE_WINDOW_MERGE_REPORT_FILENAME = "page_window_merge_report.json"
ARTIFACT_FILENAMES = (
    "document.md",
    "manifest.json",
    "report.json",
    PAGE_WINDOW_MERGE_REPORT_FILENAME,
    "sanitized_report.json",
    "rag_tables.md",
    "tables_rag.jsonl",
    "text_blocks_rag.jsonl",
    "semantic_units_rag.jsonl",
    "requirements_rag.jsonl",
    "cross_refs_rag.jsonl",
    "requirement_traceability_rag.jsonl",
    "technical_tables_rag.jsonl",
    "retrieval_chunks_rag.jsonl",
    "figures_rag.jsonl",
    "figure_descriptions_rag.jsonl",
    "figure_structures_rag.jsonl",
    "domain_units_rag.jsonl",
    "index_contract_report.json",
    "provenance_integrity_report.json",
    "artifact_integrity_report.json",
)
MERGE_SIDECAR_FILENAMES = (
    "text_blocks_rag.jsonl",
    "semantic_units_rag.jsonl",
    "requirements_rag.jsonl",
    "cross_refs_rag.jsonl",
    "requirement_traceability_rag.jsonl",
    "technical_tables_rag.jsonl",
    "tables_rag.jsonl",
    "figures_rag.jsonl",
    "figure_descriptions_rag.jsonl",
    "figure_structures_rag.jsonl",
    "domain_units_rag.jsonl",
    "retrieval_chunks_rag.jsonl",
)
MERGE_COUNT_FIELDS = {
    "text_blocks_rag.jsonl": "rag_text_block_record_count",
    "semantic_units_rag.jsonl": "semantic_unit_record_count",
    "requirements_rag.jsonl": "requirement_record_count",
    "cross_refs_rag.jsonl": "cross_ref_record_count",
    "requirement_traceability_rag.jsonl": "requirement_traceability_record_count",
    "technical_tables_rag.jsonl": "technical_table_record_count",
    "tables_rag.jsonl": "rag_table_record_count",
    "figures_rag.jsonl": "figure_rag_record_count",
    "figure_descriptions_rag.jsonl": "figure_description_record_count",
    "figure_structures_rag.jsonl": "figure_structure_record_count",
    "domain_units_rag.jsonl": "domain_unit_record_count",
    "retrieval_chunks_rag.jsonl": "retrieval_chunk_record_count",
}
MERGE_FILE_COUNT_FIELDS = {
    "text_blocks_rag.jsonl": "rag_text_block_file_count",
    "semantic_units_rag.jsonl": "semantic_unit_file_count",
    "requirements_rag.jsonl": "requirement_file_count",
    "cross_refs_rag.jsonl": "cross_ref_file_count",
    "requirement_traceability_rag.jsonl": "requirement_traceability_file_count",
    "technical_tables_rag.jsonl": "technical_table_file_count",
    "tables_rag.jsonl": "rag_table_file_count",
    "figures_rag.jsonl": "figure_rag_file_count",
    "figure_descriptions_rag.jsonl": "figure_description_file_count",
    "figure_structures_rag.jsonl": "figure_structure_file_count",
    "domain_units_rag.jsonl": "domain_unit_file_count",
    "retrieval_chunks_rag.jsonl": "retrieval_chunk_file_count",
}
SIDECAR_ID_FIELDS = {
    "text_blocks_rag.jsonl": ("block_id",),
    "semantic_units_rag.jsonl": ("semantic_id",),
    "requirements_rag.jsonl": ("semantic_id", "requirement_id", "stable_requirement_seed"),
    "cross_refs_rag.jsonl": ("ref_id",),
    "requirement_traceability_rag.jsonl": ("trace_id", "requirement_id", "stable_requirement_seed"),
    "technical_tables_rag.jsonl": (
        "technical_table_unit_id",
        "technical_table_id",
        "stable_requirement_seed",
    ),
    "tables_rag.jsonl": ("table_id", "table_row_id"),
    "figures_rag.jsonl": ("figure_id",),
    "figure_descriptions_rag.jsonl": ("description_id",),
    "figure_structures_rag.jsonl": ("structure_id",),
    "domain_units_rag.jsonl": ("domain_unit_id", "stable_requirement_seed"),
    "retrieval_chunks_rag.jsonl": ("chunk_id", "stable_requirement_seed"),
}
SOURCE_TYPE_ID_FIELDS = {
    "text_blocks_rag.jsonl": (("text_block", "block_id"),),
    "semantic_units_rag.jsonl": (("semantic_unit", "semantic_id"),),
    "requirements_rag.jsonl": (("requirement", "semantic_id"),),
    "cross_refs_rag.jsonl": (("cross_ref", "ref_id"),),
    "requirement_traceability_rag.jsonl": (("requirement_trace", "trace_id"),),
    "technical_tables_rag.jsonl": (
        ("technical_table_unit", "technical_table_unit_id"),
        ("technical_table", "technical_table_unit_id"),
    ),
    "tables_rag.jsonl": (("table_row", "table_row_id"), ("table", "table_id")),
    "figures_rag.jsonl": (("figure", "figure_id"), ("excluded_figure", "figure_id")),
    "figure_descriptions_rag.jsonl": (("figure_description", "description_id"),),
    "figure_structures_rag.jsonl": (("figure_structure", "structure_id"),),
    "domain_units_rag.jsonl": (("domain_unit", "domain_unit_id"),),
    "retrieval_chunks_rag.jsonl": (("retrieval_chunk", "chunk_id"),),
}
CHUNK_RELATIONSHIP_FIELDS = ("previous_chunk_id", "next_chunk_id", "section_anchor_chunk_id")


@dataclass(frozen=True)
class WindowJsonlRecord:
    """A sidecar record with enough origin metadata to merge deterministically."""

    file_name: str
    line_number: int
    window: dict[str, Any]
    record: dict[str, Any]


def _package_version(package_name: str) -> str | None:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None


def _resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _ensure_project_root_on_path(project_root: Path | str | None = None) -> Path:
    """Return the project root and make repository-local scripts importable."""
    root = _resolve_path(project_root or Path.cwd())
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root


def configured_roots(project_root: Path | None = None) -> list[Path]:
    """Return filesystem roots the local MCP server may read or write."""
    env_value = os.environ.get(MCP_ROOTS_ENV)
    if env_value:
        roots = [_resolve_path(item) for item in env_value.split(os.pathsep) if item.strip()]
    else:
        roots = [_resolve_path(project_root or Path.cwd())]
    return sorted(set(roots), key=lambda path: str(path))


def _allowed_roots(roots: list[Path] | None = None) -> list[Path]:
    return [_resolve_path(root) for root in (roots or configured_roots())]


def ensure_within_roots(path: str | Path, roots: list[Path], *, label: str) -> Path:
    """Resolve a path and reject access outside configured MCP roots."""
    resolved = _resolve_path(path)
    if any(resolved == root or resolved.is_relative_to(root) for root in roots):
        return resolved
    allowed = ", ".join(str(root) for root in roots)
    raise ValueError(f"{label} is outside configured MCP roots: {resolved}. Allowed roots: {allowed}")


def _optional_enum(value: str | None, enum_type: type[Any], default: str) -> Any:
    return enum_type(default if value is None else value)


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _format_page_range(pages: list[int]) -> str:
    if not pages:
        raise ValueError("Cannot format an empty page selection")
    ranges: list[str] = []
    start = previous = pages[0]
    for page in pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        ranges.append(f"{start}-{previous}" if start != previous else str(start))
        start = previous = page
    ranges.append(f"{start}-{previous}" if start != previous else str(start))
    return ",".join(ranges)


def _window_id(start_page: int, end_page: int) -> str:
    return f"pages-{start_page:04d}-{end_page:04d}"


def _window_output_subdir(window_id: str) -> str:
    return f"{WINDOW_OUTPUT_ROOT}/{window_id}"


def _selected_pages_for_pdf(input_pdf: Path, *, pages: str | None, password: str | None) -> tuple[int, list[int]]:
    reader = open_pdf_reader(input_pdf, password)
    total_pages = len(reader.pages)
    return total_pages, parse_page_range(pages, total_pages)


def _build_page_window_records(
    *,
    selected_pages: list[int],
    source_sha256: str,
    output_dir: Path,
    window_size: int,
) -> list[dict[str, Any]]:
    if window_size < 1:
        raise ValueError("window_size must be >= 1")

    windows: list[dict[str, Any]] = []
    for index, offset in enumerate(range(0, len(selected_pages), window_size), start=1):
        window_pages = selected_pages[offset : offset + window_size]
        start_page = window_pages[0]
        end_page = window_pages[-1]
        window_id = _window_id(start_page, end_page)
        output_subdir = _window_output_subdir(window_id)
        windows.append(
            {
                "window_index": index,
                "window_id": window_id,
                "page_range": _format_page_range(window_pages),
                "start_page": start_page,
                "end_page": end_page,
                "selected_pages": window_pages,
                "selected_page_count": len(window_pages),
                "source_sha256": source_sha256,
                "output_subdir": output_subdir,
                "output_dir": str(output_dir / WINDOW_OUTPUT_ROOT / window_id),
            }
        )
    return windows


def list_profiles() -> dict[str, Any]:
    """Return supported local RAG profiles and their deterministic option bundles."""
    return {
        "schema_version": "1.0",
        "profiles": {
            profile: asdict(rag_profile_options(profile))
            for profile in SUPPORTED_RAG_PURPOSE_PROFILES
        },
        "domain_adapters": [mode.value for mode in DomainAdapterMode],
        "image_modes": [mode.value for mode in ImageMode],
        "table_modes": [mode.value for mode in TableMode],
        "rag_table_outputs": [mode.value for mode in RagTableOutputMode],
        "output_profiles": [profile.value for profile in OutputProfile],
        "rag_sidecar_scopes": [scope.value for scope in RagSidecarScope],
    }


def plan_page_windows(
    *,
    input_pdf: str,
    output_dir: str | None = None,
    pages: str | None = None,
    password: str | None = None,
    window_size: int = 100,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Plan deterministic page windows for a large PDF conversion."""
    allowed_roots = _allowed_roots(roots)
    resolved_input = ensure_within_roots(input_pdf, allowed_roots, label="input_pdf")
    if output_dir is None:
        resolved_output = default_output_dir_for_input(resolved_input)
        ensure_within_roots(resolved_output, allowed_roots, label="output_dir")
    else:
        resolved_output = ensure_within_roots(output_dir, allowed_roots, label="output_dir")
    total_pages, selected_pages = _selected_pages_for_pdf(resolved_input, pages=pages, password=password)
    source_sha256 = _file_sha256(resolved_input)
    windows = _build_page_window_records(
        selected_pages=selected_pages,
        source_sha256=source_sha256,
        output_dir=resolved_output,
        window_size=window_size,
    )
    return {
        "schema_version": "1.0",
        "purpose": "page_window_plan",
        "input_pdf": str(resolved_input),
        "output_dir": str(resolved_output),
        "source_sha256": source_sha256,
        "total_pages": total_pages,
        "selected_pages": selected_pages,
        "selected_page_count": len(selected_pages),
        "window_size": window_size,
        "window_count": len(windows),
        "windows": windows,
        "password_supplied": password is not None,
    }


def _find_window(plan: dict[str, Any], window_id: str) -> dict[str, Any]:
    for window in plan["windows"]:
        if window["window_id"] == window_id:
            return window
    raise ValueError(f"window_id not found in page-window plan: {window_id}")


def convert_page_window(
    *,
    input_pdf: str,
    output_dir: str | None = None,
    window_id: str,
    pages: str | None = None,
    password: str | None = None,
    window_size: int = 100,
    rag_profile: str = "preserve",
    domain_adapter: str | None = None,
    manual_domain_adapter_label: str | None = None,
    manual_domain_adapter_keywords: str | None = None,
    image_mode: str | None = None,
    table_mode: str | None = None,
    rag_table_output: str | None = None,
    output_profile: str = OutputProfile.FULL.value,
    rag_sidecar_scope: str | None = None,
    force_ocr: bool = False,
    ocr_lang: str = "eng",
    ocr_backend: str = "tesseract",
    page_workers: int = 1,
    assetless_figure_text: bool = False,
    image_extraction_page_timeout_seconds: float | None = None,
    image_extraction_stage_timeout_seconds: float | None = None,
    figure_semantics_stage_timeout_seconds: float | None = None,
    require_domain_adapter_for_technical_profile: bool = True,
    skip_existing: bool = False,
    warning_limit: int = DEFAULT_WARNING_LIMIT,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Convert one planned page window into its stable windows/pages-* output directory."""
    allowed_roots = _allowed_roots(roots)
    plan = plan_page_windows(
        input_pdf=input_pdf,
        output_dir=output_dir,
        pages=pages,
        password=password,
        window_size=window_size,
        roots=allowed_roots,
    )
    window = _find_window(plan, window_id)
    conversion = convert_pdf(
        input_pdf=input_pdf,
        output_dir=window["output_dir"],
        rag_profile=rag_profile,
        domain_adapter=domain_adapter,
        manual_domain_adapter_label=manual_domain_adapter_label,
        manual_domain_adapter_keywords=manual_domain_adapter_keywords,
        pages=window["page_range"],
        password=password,
        image_mode=image_mode,
        table_mode=table_mode,
        rag_table_output=rag_table_output,
        output_profile=output_profile,
        rag_sidecar_scope=rag_sidecar_scope,
        force_ocr=force_ocr,
        ocr_lang=ocr_lang,
        ocr_backend=ocr_backend,
        page_workers=page_workers,
        assetless_figure_text=assetless_figure_text,
        image_extraction_page_timeout_seconds=image_extraction_page_timeout_seconds,
        image_extraction_stage_timeout_seconds=image_extraction_stage_timeout_seconds,
        figure_semantics_stage_timeout_seconds=figure_semantics_stage_timeout_seconds,
        require_domain_adapter_for_technical_profile=require_domain_adapter_for_technical_profile,
        skip_existing=skip_existing,
        warning_limit=warning_limit,
        roots=allowed_roots,
    )
    return {
        "schema_version": "1.0",
        "purpose": "page_window_conversion",
        "source_sha256": plan["source_sha256"],
        "window": window,
        "conversion": conversion,
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _read_jsonl(path: Path, *, window: dict[str, Any], file_name: str) -> list[WindowJsonlRecord]:
    if not path.exists():
        return []
    records: list[WindowJsonlRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSONL object in {path}:{line_number}")
        records.append(WindowJsonlRecord(file_name=file_name, line_number=line_number, window=window, record=payload))
    return records


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        if path.exists():
            path.unlink()
        return
    text = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    path.write_text(text, encoding="utf-8")


def _record_id_value(record: dict[str, Any]) -> str:
    for field in (
        "chunk_id",
        "block_id",
        "semantic_id",
        "trace_id",
        "ref_id",
        "technical_table_unit_id",
        "table_row_id",
        "figure_id",
        "description_id",
        "structure_id",
        "domain_unit_id",
        "table_id",
    ):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _record_page(record: dict[str, Any]) -> int:
    page = record.get("page")
    if isinstance(page, int) and page >= 1:
        return page
    page_range = record.get("page_range")
    if isinstance(page_range, list) and page_range and isinstance(page_range[0], int):
        return page_range[0]
    source_refs = record.get("source_refs")
    if isinstance(source_refs, list):
        pages = [
            ref.get("page")
            for ref in source_refs
            if isinstance(ref, dict) and isinstance(ref.get("page"), int) and ref["page"] >= 1
        ]
        if pages:
            return min(pages)
    return 0


def _record_bbox_top(record: dict[str, Any]) -> float:
    bbox = record.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 2 and isinstance(bbox[1], (int, float)):
        return float(bbox[1])
    source_refs = record.get("source_refs")
    if isinstance(source_refs, list):
        tops = [
            float(ref["bbox"][1])
            for ref in source_refs
            if isinstance(ref, dict)
            and isinstance(ref.get("bbox"), list)
            and len(ref["bbox"]) >= 2
            and isinstance(ref["bbox"][1], (int, float))
        ]
        if tops:
            return min(tops)
    return 1_000_000.0


def _record_sort_key(item: WindowJsonlRecord) -> tuple[int, float, int, int, str]:
    window_index = int(item.window.get("window_index") or 0)
    return (
        _record_page(item.record),
        _record_bbox_top(item.record),
        window_index,
        item.line_number,
        _record_id_value(item.record),
    )


def _collision_scoped_id(window_id: str, value: str) -> str:
    return f"{window_id}__{value}"


def _build_field_id_map(
    records_by_file: dict[str, list[WindowJsonlRecord]],
) -> tuple[dict[tuple[str, str, str], str], int, int]:
    occurrences: dict[tuple[str, str], list[WindowJsonlRecord]] = {}
    for file_name, records in records_by_file.items():
        for item in records:
            if file_name == "retrieval_chunks_rag.jsonl":
                fields = tuple(field for field in SIDECAR_ID_FIELDS[file_name] if field != "chunk_id")
            else:
                fields = SIDECAR_ID_FIELDS.get(file_name, ())
            for field in fields:
                value = item.record.get(field)
                if isinstance(value, str) and value.strip():
                    occurrences.setdefault((field, value), []).append(item)

    field_map: dict[tuple[str, str, str], str] = {}
    collision_count = 0
    rewritten_count = 0
    for (field, value), items in occurrences.items():
        window_ids = {str(item.window["window_id"]) for item in items}
        if len(window_ids) <= 1:
            continue
        collision_count += 1
        for item in items:
            window_id = str(item.window["window_id"])
            field_map[(window_id, field, value)] = _collision_scoped_id(window_id, value)
            rewritten_count += 1
    return field_map, collision_count, rewritten_count


def _build_source_id_map(
    records_by_file: dict[str, list[WindowJsonlRecord]],
    field_id_map: dict[tuple[str, str, str], str],
) -> dict[tuple[str, str, str], str]:
    source_map: dict[tuple[str, str, str], str] = {}
    for file_name, records in records_by_file.items():
        for item in records:
            window_id = str(item.window["window_id"])
            for source_type, id_field in SOURCE_TYPE_ID_FIELDS.get(file_name, ()):
                value = item.record.get(id_field)
                if not isinstance(value, str) or not value.strip():
                    continue
                source_map[(window_id, source_type, value)] = field_id_map.get((window_id, id_field, value), value)
    return source_map


def _rewrite_source_refs(
    source_refs: Any,
    *,
    window_id: str,
    source_id_map: dict[tuple[str, str, str], str],
) -> None:
    if not isinstance(source_refs, list):
        return
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        source_type = ref.get("source_type")
        source_id = ref.get("source_id")
        if isinstance(source_type, str) and isinstance(source_id, str):
            ref["source_id"] = source_id_map.get((window_id, source_type, source_id), source_id)
        if "table_id" in ref and isinstance(ref["table_id"], str):
            ref["table_id"] = source_id_map.get((window_id, "table", ref["table_id"]), ref["table_id"])


def _update_source_dedupe_key(record: dict[str, Any]) -> None:
    source_refs = record.get("source_refs")
    if not isinstance(source_refs, list):
        return
    source_ids = [
        str(ref["source_id"])
        for ref in source_refs
        if isinstance(ref, dict) and isinstance(ref.get("source_id"), str) and ref["source_id"].strip()
    ]
    if source_ids:
        record["source_dedupe_key"] = "|".join(sorted(source_ids))


def _rewrite_chunk_relationships(
    record: dict[str, Any],
    *,
    window_id: str,
    chunk_id_map: dict[tuple[str, str], str],
) -> None:
    for field in CHUNK_RELATIONSHIP_FIELDS:
        value = record.get(field)
        if isinstance(value, str):
            replacement = chunk_id_map.get((window_id, value))
            if replacement is None:
                record.pop(field, None)
            else:
                record[field] = replacement
    for field in ("related_chunk_ids", "merged_source_chunk_ids"):
        values = record.get(field)
        if not isinstance(values, list):
            continue
        rewritten = [
            chunk_id_map[(window_id, value)]
            for value in values
            if isinstance(value, str) and (window_id, value) in chunk_id_map
        ]
        record[field] = rewritten


def _rewrite_record(
    item: WindowJsonlRecord,
    *,
    source_sha256: str | None,
    field_id_map: dict[tuple[str, str, str], str],
    source_id_map: dict[tuple[str, str, str], str],
    chunk_id_map: dict[tuple[str, str], str],
    chunk_index: int | None = None,
) -> dict[str, Any]:
    window_id = str(item.window["window_id"])
    record = json.loads(json.dumps(item.record, ensure_ascii=False))
    for field in SIDECAR_ID_FIELDS.get(item.file_name, ()):
        value = record.get(field)
        if isinstance(value, str):
            if item.file_name == "retrieval_chunks_rag.jsonl" and field == "chunk_id":
                record[field] = chunk_id_map[(window_id, value)]
            else:
                record[field] = field_id_map.get((window_id, field, value), value)

    for field, source_type in (
        ("figure_id", "figure"),
        ("table_id", "table"),
        ("table_row_id", "table_row"),
        ("related_command_unit_id", "technical_table_unit"),
    ):
        value = record.get(field)
        if isinstance(value, str):
            record[field] = source_id_map.get((window_id, source_type, value), record[field])

    if source_sha256 is not None and isinstance(record.get("source_sha256"), str):
        record["source_sha256"] = source_sha256
    if chunk_index is not None:
        record["chunk_index"] = chunk_index
    record["source_window_id"] = window_id
    record["source_window_page_range"] = item.window["page_range"]
    _rewrite_source_refs(record.get("source_refs"), window_id=window_id, source_id_map=source_id_map)
    if item.file_name == "retrieval_chunks_rag.jsonl":
        _rewrite_chunk_relationships(record, window_id=window_id, chunk_id_map=chunk_id_map)
    _update_source_dedupe_key(record)
    return record


def _load_window_records(windows: list[dict[str, Any]]) -> dict[str, list[WindowJsonlRecord]]:
    records_by_file: dict[str, list[WindowJsonlRecord]] = {file_name: [] for file_name in MERGE_SIDECAR_FILENAMES}
    for window in windows:
        window_dir = Path(str(window["output_dir"]))
        for file_name in MERGE_SIDECAR_FILENAMES:
            records_by_file[file_name].extend(_read_jsonl(window_dir / file_name, window=window, file_name=file_name))
    return records_by_file


def _merge_sidecars(
    *,
    output_dir: Path,
    windows: list[dict[str, Any]],
    source_sha256: str | None,
) -> tuple[dict[str, int], int, int]:
    records_by_file = _load_window_records(windows)
    field_id_map, id_collision_count, rewritten_id_count = _build_field_id_map(records_by_file)
    source_id_map = _build_source_id_map(records_by_file, field_id_map)

    retrieval_records = sorted(records_by_file["retrieval_chunks_rag.jsonl"], key=_record_sort_key)
    chunk_id_map: dict[tuple[str, str], str] = {}
    for chunk_index, item in enumerate(retrieval_records, start=1):
        old_chunk_id = item.record.get("chunk_id")
        if isinstance(old_chunk_id, str):
            window_id = str(item.window["window_id"])
            chunk_id_map[(window_id, old_chunk_id)] = f"chunk-{chunk_index:06d}"
            source_id_map[(window_id, "retrieval_chunk", old_chunk_id)] = f"chunk-{chunk_index:06d}"
            if old_chunk_id != f"chunk-{chunk_index:06d}":
                rewritten_id_count += 1

    merged_counts: dict[str, int] = {}
    for file_name in MERGE_SIDECAR_FILENAMES:
        sorted_records = sorted(records_by_file[file_name], key=_record_sort_key)
        merged_records: list[dict[str, Any]] = []
        for index, item in enumerate(sorted_records, start=1):
            chunk_index = index if file_name == "retrieval_chunks_rag.jsonl" else None
            merged_records.append(
                _rewrite_record(
                    item,
                    source_sha256=source_sha256,
                    field_id_map=field_id_map,
                    source_id_map=source_id_map,
                    chunk_id_map=chunk_id_map,
                    chunk_index=chunk_index,
                )
            )
        _write_jsonl(output_dir / file_name, merged_records)
        merged_counts[file_name] = len(merged_records)
    return merged_counts, id_collision_count, rewritten_id_count


def _copy_window_assets(*, output_dir: Path, windows: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    for window in windows:
        window_dir = Path(str(window["output_dir"]))
        assets_dir = window_dir / "assets"
        if not assets_dir.exists():
            continue
        for source_path in sorted(path for path in assets_dir.rglob("*") if path.is_file()):
            relative = source_path.relative_to(window_dir)
            target_path = output_dir / relative
            if target_path.exists() and target_path.read_bytes() != source_path.read_bytes():
                warnings.append(
                    {
                        "code": "asset_collision",
                        "message": "Window asset path collision was left unchanged.",
                        "window_id": window["window_id"],
                        "path": relative.as_posix(),
                    }
                )
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


def _merge_markdown(*, output_dir: Path, windows: list[dict[str, Any]]) -> None:
    parts: list[str] = []
    for window in windows:
        path = Path(str(window["output_dir"])) / "document.md"
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
    (output_dir / "document.md").write_text("\n\n".join(parts).rstrip() + "\n", encoding="utf-8")


def _sort_manifest_records(records: list[Any]) -> list[Any]:
    return sorted(
        records,
        key=lambda item: (
            _record_page(item) if isinstance(item, dict) else 0,
            _record_bbox_top(item) if isinstance(item, dict) else 1_000_000.0,
            _record_id_value(item) if isinstance(item, dict) else "",
        ),
    )


def _merge_manifest(*, output_dir: Path, windows: list[dict[str, Any]], source_sha256: str | None) -> dict[str, Any]:
    manifests = [_read_json(Path(str(window["output_dir"])) / "manifest.json") for window in windows]
    merged = dict(manifests[0])
    selected_pages = sorted({page for manifest in manifests for page in manifest.get("selected_pages", [])})
    merged["selected_pages"] = selected_pages
    merged["total_pages"] = max(int(manifest.get("total_pages") or 0) for manifest in manifests)
    merged["images"] = _sort_manifest_records([item for manifest in manifests for item in manifest.get("images", [])])
    merged["excluded_images"] = _sort_manifest_records(
        [item for manifest in manifests for item in manifest.get("excluded_images", [])]
    )
    merged["tables"] = _sort_manifest_records([item for manifest in manifests for item in manifest.get("tables", [])])
    merged["ocr_pages"] = sorted({page for manifest in manifests for page in manifest.get("ocr_pages", [])})
    merged["warnings"] = [
        {
            **warning,
            "details": {
                **(warning.get("details") if isinstance(warning.get("details"), dict) else {}),
                "source_window_id": window["window_id"],
                "source_window_page_range": window["page_range"],
            },
        }
        for manifest, window in zip(manifests, windows)
        for warning in manifest.get("warnings", [])
        if isinstance(warning, dict)
    ]
    options = dict(merged.get("options") if isinstance(merged.get("options"), dict) else {})
    options.update(
        {
            "page_window_merge": True,
            "page_window_count": len(windows),
            "page_window_output_root": WINDOW_OUTPUT_ROOT,
        }
    )
    if source_sha256 is not None:
        options["source_pdf_sha256"] = source_sha256
    merged["options"] = options
    _write_json(output_dir / "manifest.json", merged)
    return merged


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _merge_report(
    *,
    output_dir: Path,
    windows: list[dict[str, Any]],
    manifest: dict[str, Any],
    merged_counts: dict[str, int],
) -> dict[str, Any]:
    reports = [_read_json(Path(str(window["output_dir"])) / "report.json") for window in windows]
    started_values = [value for value in (_parse_dt(report.get("started_at")) for report in reports) if value is not None]
    finished_values = [value for value in (_parse_dt(report.get("finished_at")) for report in reports) if value is not None]
    started_at = min(started_values) if started_values else datetime.now(timezone.utc)
    finished_at = max(finished_values) if finished_values else datetime.now(timezone.utc)
    statuses = {str(report.get("status")) for report in reports}
    status = "failed" if "failed" in statuses else ("partial_success" if "partial_success" in statuses else "success")
    warnings = [
        {
            **warning,
            "details": {
                **(warning.get("details") if isinstance(warning.get("details"), dict) else {}),
                "source_window_id": window["window_id"],
                "source_window_page_range": window["page_range"],
            },
        }
        for report, window in zip(reports, windows)
        for warning in report.get("warnings", [])
        if isinstance(warning, dict)
    ]
    page_results = _sort_manifest_records(
        [item for report in reports for item in report.get("page_results", []) if isinstance(item, dict)]
    )
    stage_durations: dict[str, int] = {}
    engine_usage: dict[str, bool] = {}
    for report in reports:
        for engine, used in (report.get("engine_usage") or {}).items():
            engine_usage[str(engine)] = bool(engine_usage.get(str(engine), False) or used)
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        for stage, duration in (summary.get("stage_durations_ms") or {}).items():
            if isinstance(duration, int):
                stage_durations[str(stage)] = stage_durations.get(str(stage), 0) + duration
    summary = dict(reports[0].get("summary") if isinstance(reports[0].get("summary"), dict) else {})
    summary.update(
        {
            "processed_pages": len(manifest.get("selected_pages", [])),
            "warning_count": len(warnings),
            "failed_page_count": len({page for report in reports for page in report.get("failed_pages", [])}),
            "partial_success": status == "partial_success",
            "stage_durations_ms": {**stage_durations, "page_window_merge": 0},
            "page_status_counts": {
                "success": sum(1 for item in page_results if item.get("status") == "success"),
                "partial_success": sum(1 for item in page_results if item.get("status") == "partial_success"),
                "failed": sum(1 for item in page_results if item.get("status") == "failed"),
            },
            "table_total": len(manifest.get("tables", [])),
        }
    )
    for file_name, field_name in MERGE_COUNT_FIELDS.items():
        summary[field_name] = merged_counts.get(file_name, 0)
    for file_name, field_name in MERGE_FILE_COUNT_FIELDS.items():
        summary[field_name] = int(merged_counts.get(file_name, 0) > 0)
    report_payload = {
        "schema_version": "1.0",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": sum(int(report.get("duration_ms") or 0) for report in reports),
        "status": status,
        "engine_usage": engine_usage,
        "failed_pages": sorted({page for report in reports for page in report.get("failed_pages", [])}),
        "warnings": warnings,
        "page_results": page_results,
        "summary": summary,
    }
    _write_json(output_dir / "report.json", report_payload)
    return report_payload


def _window_summary(window: dict[str, Any]) -> dict[str, Any]:
    report = _read_optional_json(Path(str(window["output_dir"])) / "report.json")
    return {
        "window_id": window["window_id"],
        "source_window_page_range": window["page_range"],
        "selected_pages": window["selected_pages"],
        "output_subdir": window["output_subdir"],
        "output_dir": window["output_dir"],
        "status": report.get("status") if isinstance(report, dict) else None,
    }


def _window_record_from_dir(index: int, path: Path) -> dict[str, Any]:
    raw_range = path.name.removeprefix("pages-")
    start_page = 0
    end_page = 0
    selected_pages: list[int] = []
    page_range = raw_range
    parts = raw_range.split("-", maxsplit=1)
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        start_page = int(parts[0])
        end_page = int(parts[1])
        if start_page >= 1 and end_page >= start_page:
            selected_pages = list(range(start_page, end_page + 1))
            page_range = f"{start_page}-{end_page}" if start_page != end_page else str(start_page)
    return {
        "window_index": index,
        "window_id": path.name,
        "page_range": page_range,
        "start_page": start_page,
        "end_page": end_page,
        "selected_pages": selected_pages,
        "output_subdir": f"{WINDOW_OUTPUT_ROOT}/{path.name}",
        "output_dir": str(path),
    }


def _validate_output_if_requested(
    *,
    output_dir: Path,
    roots: list[Path],
    project_root: Path | str | None,
    enabled: bool,
) -> dict[str, Any] | None:
    if not enabled:
        return None
    return validate_output(output_dir=str(output_dir), roots=roots, project_root=project_root)


def merge_window_outputs(
    *,
    input_pdf: str | None = None,
    output_dir: str,
    pages: str | None = None,
    password: str | None = None,
    window_size: int = 100,
    validate_windows: bool = True,
    validate_merged: bool = True,
    roots: list[Path] | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Merge page-window conversion outputs into the final public output directory."""
    allowed_roots = _allowed_roots(roots)
    resolved_output = ensure_within_roots(output_dir, allowed_roots, label="output_dir")
    if input_pdf is not None:
        plan = plan_page_windows(
            input_pdf=input_pdf,
            output_dir=str(resolved_output),
            pages=pages,
            password=password,
            window_size=window_size,
            roots=allowed_roots,
        )
        source_sha256 = str(plan["source_sha256"])
        windows = list(plan["windows"])
    else:
        source_sha256 = None
        windows_root = resolved_output / WINDOW_OUTPUT_ROOT
        windows = [
            _window_record_from_dir(index, path)
            for index, path in enumerate(sorted(item for item in windows_root.iterdir() if item.is_dir()), start=1)
        ]
    if not windows:
        raise ValueError("No page-window outputs found to merge")
    for window in windows:
        window_dir = ensure_within_roots(window["output_dir"], allowed_roots, label="window.output_dir")
        window["output_dir"] = str(window_dir)
        if not (window_dir / "manifest.json").exists() or not (window_dir / "report.json").exists():
            raise FileNotFoundError(f"Window output is missing manifest.json or report.json: {window_dir}")

    warnings: list[dict[str, Any]] = []
    window_validations = [
        _validate_output_if_requested(
            output_dir=Path(str(window["output_dir"])),
            roots=allowed_roots,
            project_root=project_root,
            enabled=validate_windows,
        )
        for window in windows
    ]
    _copy_window_assets(output_dir=resolved_output, windows=windows, warnings=warnings)
    _merge_markdown(output_dir=resolved_output, windows=windows)
    merged_counts, id_collision_count, rewritten_id_count = _merge_sidecars(
        output_dir=resolved_output,
        windows=windows,
        source_sha256=source_sha256,
    )
    manifest = _merge_manifest(output_dir=resolved_output, windows=windows, source_sha256=source_sha256)
    _merge_report(output_dir=resolved_output, windows=windows, manifest=manifest, merged_counts=merged_counts)
    merged_validation = _validate_output_if_requested(
        output_dir=resolved_output,
        roots=allowed_roots,
        project_root=project_root,
        enabled=validate_merged,
    )
    validation_summary = {
        "windows": [
            {
                "window_id": window["window_id"],
                "status": validation.get("status") if isinstance(validation, dict) else None,
                "passed": validation.get("passed") if isinstance(validation, dict) else None,
                "summary": validation.get("summary") if isinstance(validation, dict) else None,
            }
            for window, validation in zip(windows, window_validations)
        ],
        "merged": {
            "status": merged_validation.get("status") if isinstance(merged_validation, dict) else None,
            "passed": merged_validation.get("passed") if isinstance(merged_validation, dict) else None,
            "summary": merged_validation.get("summary") if isinstance(merged_validation, dict) else None,
        }
        if isinstance(merged_validation, dict)
        else None,
    }
    merge_report = {
        "schema_version": "1.0",
        "purpose": "page_window_merge",
        "source_pdf_sha256": source_sha256,
        "output_dir": str(resolved_output),
        "window_count": len(windows),
        "windows": [_window_summary(window) for window in windows],
        "merged_record_counts": merged_counts,
        "id_collision_count": id_collision_count,
        "rewritten_id_count": rewritten_id_count,
        "validation_summary": validation_summary,
        "warnings": warnings,
    }
    merge_report_path = resolved_output / PAGE_WINDOW_MERGE_REPORT_FILENAME
    _write_json(merge_report_path, merge_report)
    status = "success"
    if warnings or (
        isinstance(merged_validation, dict)
        and not bool(merged_validation.get("passed"))
    ):
        status = "warning"
    return {
        "schema_version": "1.0",
        "purpose": "page_window_merge",
        "status": status,
        "output_dir": str(resolved_output),
        "merge_report_uri": merge_report_path.resolve().as_uri(),
        "artifact_uris": _artifact_map(resolved_output),
        "source_pdf_sha256": source_sha256,
        "window_count": len(windows),
        "merged_record_counts": merged_counts,
        "id_collision_count": id_collision_count,
        "rewritten_id_count": rewritten_id_count,
        "validation_summary": validation_summary,
        "warning_count": len(warnings),
        "warnings_preview": warnings[:DEFAULT_WARNING_LIMIT],
    }


def convert_pdf_windowed(
    *,
    input_pdf: str,
    output_dir: str | None = None,
    pages: str | None = None,
    password: str | None = None,
    window_size: int = 100,
    rag_profile: str = "preserve",
    domain_adapter: str | None = None,
    manual_domain_adapter_label: str | None = None,
    manual_domain_adapter_keywords: str | None = None,
    image_mode: str | None = None,
    table_mode: str | None = None,
    rag_table_output: str | None = None,
    output_profile: str = OutputProfile.FULL.value,
    rag_sidecar_scope: str | None = None,
    force_ocr: bool = False,
    ocr_lang: str = "eng",
    ocr_backend: str = "tesseract",
    page_workers: int = 1,
    assetless_figure_text: bool = False,
    image_extraction_page_timeout_seconds: float | None = None,
    image_extraction_stage_timeout_seconds: float | None = None,
    figure_semantics_stage_timeout_seconds: float | None = None,
    require_domain_adapter_for_technical_profile: bool = True,
    skip_existing: bool = False,
    validate_windows: bool = True,
    validate_merged: bool = True,
    warning_limit: int = DEFAULT_WARNING_LIMIT,
    roots: list[Path] | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Plan, convert, validate, and merge deterministic page windows for one PDF."""
    allowed_roots = _allowed_roots(roots)
    plan = plan_page_windows(
        input_pdf=input_pdf,
        output_dir=output_dir,
        pages=pages,
        password=password,
        window_size=window_size,
        roots=allowed_roots,
    )
    conversions: list[dict[str, Any]] = []
    for window in plan["windows"]:
        try:
            conversion = convert_page_window(
                input_pdf=input_pdf,
                output_dir=plan["output_dir"],
                window_id=window["window_id"],
                pages=pages,
                password=password,
                window_size=window_size,
                rag_profile=rag_profile,
                domain_adapter=domain_adapter,
                manual_domain_adapter_label=manual_domain_adapter_label,
                manual_domain_adapter_keywords=manual_domain_adapter_keywords,
                image_mode=image_mode,
                table_mode=table_mode,
                rag_table_output=rag_table_output,
                output_profile=output_profile,
                rag_sidecar_scope=rag_sidecar_scope,
                force_ocr=force_ocr,
                ocr_lang=ocr_lang,
                ocr_backend=ocr_backend,
                page_workers=page_workers,
                assetless_figure_text=assetless_figure_text,
                image_extraction_page_timeout_seconds=image_extraction_page_timeout_seconds,
                image_extraction_stage_timeout_seconds=image_extraction_stage_timeout_seconds,
                figure_semantics_stage_timeout_seconds=figure_semantics_stage_timeout_seconds,
                require_domain_adapter_for_technical_profile=require_domain_adapter_for_technical_profile,
                skip_existing=skip_existing,
                warning_limit=warning_limit,
                roots=allowed_roots,
            )
        except Exception as exc:  # noqa: BLE001
            conversions.append(
                {
                    "window_id": window["window_id"],
                    "status": "failed",
                    "error": str(exc),
                }
            )
            return {
                "schema_version": "1.0",
                "purpose": "page_windowed_conversion",
                "status": "failed",
                "output_dir": plan["output_dir"],
                "source_sha256": plan["source_sha256"],
                "window_count": plan["window_count"],
                "conversions": conversions,
                "merge": None,
            }
        conversions.append(
            {
                "window_id": window["window_id"],
                "status": conversion["conversion"]["status"],
                "exit_code": conversion["conversion"]["exit_code"],
                "output_dir": conversion["conversion"]["output_dir"],
                "warning_count": conversion["conversion"]["warning_count"],
                "report_summary": conversion["conversion"]["report_summary"],
            }
        )

    merge = merge_window_outputs(
        input_pdf=input_pdf,
        output_dir=plan["output_dir"],
        pages=pages,
        password=password,
        window_size=window_size,
        validate_windows=validate_windows,
        validate_merged=validate_merged,
        roots=allowed_roots,
        project_root=project_root,
    )
    failed_count = sum(1 for conversion in conversions if conversion["status"] == "failed")
    partial_count = sum(1 for conversion in conversions if conversion["status"] == "partial_success")
    return {
        "schema_version": "1.0",
        "purpose": "page_windowed_conversion",
        "status": "failed" if failed_count else ("partial_success" if partial_count else merge["status"]),
        "output_dir": plan["output_dir"],
        "source_sha256": plan["source_sha256"],
        "window_count": plan["window_count"],
        "conversions": conversions,
        "merge": merge,
    }


def doctor(
    *,
    skip_ocr_check: bool = False,
    ocr_lang: str = "eng",
    roots: list[Path] | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Return local server readiness without making external service calls."""
    if project_root is not None:
        _ensure_project_root_on_path(project_root)
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "ok",
        "server": SERVER_NAME,
        "package_version": _package_version("pdf2md"),
        "mcp_sdk_available": _mcp_sdk_available(),
        "mcp_extra": MCP_EXTRA,
        "roots_env": MCP_ROOTS_ENV,
        "roots": [str(root) for root in (roots or configured_roots())],
        "ocr_backends": list(SUPPORTED_OCR_BACKENDS),
        "ocr_check": None,
    }
    if skip_ocr_check:
        return result

    try:
        from scripts.check_ocr_runtime import check_ocr_runtime

        ocr_report = check_ocr_runtime(ocr_lang=ocr_lang)
        result["ocr_check"] = ocr_report
        checks = ocr_report.get("checks", {})
        if not checks.get("tesseract_executable", {}).get("ok", False):
            result["status"] = "warning"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "warning"
        result["ocr_check"] = {"status": "error", "message": str(exc)}
    return result


def _mcp_sdk_available() -> bool:
    try:
        import mcp.server.fastmcp  # noqa: F401
    except ImportError:
        return False
    return True


def _require_fastmcp() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            f"The MCP SDK is not installed. Install this server with `pip install -e .[mcp]` "
            f"or `pip install {MCP_EXTRA}` before running `pdf2md-mcp`."
        ) from exc
    return FastMCP


def _build_config(
    *,
    input_pdf: Path,
    output_dir: Path | None,
    rag_profile: str,
    domain_adapter: str | None,
    manual_domain_adapter_label: str | None,
    manual_domain_adapter_keywords: str | None,
    pages: str | None,
    password: str | None,
    image_mode: str | None,
    table_mode: str | None,
    rag_table_output: str | None,
    output_profile: str,
    rag_sidecar_scope: str | None,
    force_ocr: bool,
    ocr_lang: str,
    ocr_backend: str,
    page_workers: int,
    assetless_figure_text: bool,
    image_extraction_page_timeout_seconds: float | None,
    image_extraction_stage_timeout_seconds: float | None,
    figure_semantics_stage_timeout_seconds: float | None,
    require_domain_adapter_for_technical_profile: bool,
    skip_existing: bool,
) -> Config:
    profile_options = rag_profile_options(rag_profile)
    selected_domain_adapter = domain_adapter if domain_adapter is not None else profile_options.domain_adapter
    if (
        require_domain_adapter_for_technical_profile
        and rag_profile in TECHNICAL_SPEC_RAG_PROFILES
        and selected_domain_adapter == DomainAdapterMode.NONE.value
    ):
        raise ValueError("technical spec RAG profiles require a non-none domain_adapter when strict validation is enabled.")

    selected_image_mode = image_mode if image_mode is not None else profile_options.image_mode
    selected_rag_figure_text = profile_options.rag_figure_text_chunks
    if assetless_figure_text:
        selected_image_mode = ImageMode.PLACEHOLDER.value
        selected_rag_figure_text = True

    return Config(
        input_pdf=input_pdf,
        output_dir=output_dir or default_output_dir_for_input(input_pdf),
        pages=pages,
        password=password,
        image_mode=_optional_enum(selected_image_mode, ImageMode, profile_options.image_mode),
        table_mode=_optional_enum(table_mode, TableMode, profile_options.table_mode),
        rag_table_output=_optional_enum(rag_table_output, RagTableOutputMode, profile_options.rag_table_output),
        output_profile=OutputProfile(output_profile),
        rag_sidecar_scope=RagSidecarScope(rag_sidecar_scope) if rag_sidecar_scope is not None else None,
        rag_profile=rag_profile,
        domain_adapter=DomainAdapterMode(selected_domain_adapter),
        manual_domain_adapter_label=manual_domain_adapter_label,
        manual_domain_adapter_keywords=manual_domain_adapter_keywords,
        confidential_safe_mode=profile_options.confidential_safe_mode,
        force_ocr=force_ocr or profile_options.force_ocr,
        ocr_lang=ocr_lang,
        ocr_backend=ocr_backend,
        keep_page_markers=profile_options.keep_page_markers,
        remove_header_footer=profile_options.remove_header_footer,
        dedupe_images=profile_options.dedupe_images,
        repair_hyphenation=profile_options.repair_hyphenation,
        figure_crop_fallback=profile_options.figure_crop_fallback,
        image_extraction_page_timeout_seconds=image_extraction_page_timeout_seconds,
        image_extraction_stage_timeout_seconds=image_extraction_stage_timeout_seconds,
        figure_semantics_stage_timeout_seconds=figure_semantics_stage_timeout_seconds,
        retrieval_chunk_max_tokens=profile_options.retrieval_chunk_max_tokens,
        retrieval_tokenizer=profile_options.retrieval_tokenizer,
        rag_contextual_embedding_text=profile_options.rag_contextual_embedding_text,
        rag_merge_sibling_text_chunks=profile_options.rag_merge_sibling_text_chunks,
        rag_chunk_relationship_metadata=profile_options.rag_chunk_relationship_metadata,
        rag_figure_text_chunks=selected_rag_figure_text,
        figure_region_ocr=profile_options.figure_region_ocr,
        rag_generated_figure_descriptions=profile_options.rag_generated_figure_descriptions,
        figure_description_backend=profile_options.figure_description_backend,
        figure_structure_extraction=profile_options.figure_structure_extraction,
        page_workers=page_workers,
        skip_existing=skip_existing,
    )


def _artifact_map(output_dir: Path) -> dict[str, str]:
    return {
        name: (output_dir / name).resolve().as_uri()
        for name in ARTIFACT_FILENAMES
        if (output_dir / name).exists()
    }


def _warning_preview(result: ConversionResult, limit: int) -> list[dict[str, Any]]:
    warnings = result.warnings[: max(limit, 0)]
    return [
        {
            "code": warning.code,
            "page": warning.page,
            "message": warning.message,
            "details": warning.details,
        }
        for warning in warnings
    ]


def _report_summary(result: ConversionResult) -> dict[str, Any] | None:
    if result.report is None:
        return None
    return result.report.summary.model_dump(mode="json")


def convert_pdf(
    *,
    input_pdf: str,
    output_dir: str | None = None,
    rag_profile: str = "preserve",
    domain_adapter: str | None = None,
    manual_domain_adapter_label: str | None = None,
    manual_domain_adapter_keywords: str | None = None,
    pages: str | None = None,
    password: str | None = None,
    image_mode: str | None = None,
    table_mode: str | None = None,
    rag_table_output: str | None = None,
    output_profile: str = OutputProfile.FULL.value,
    rag_sidecar_scope: str | None = None,
    force_ocr: bool = False,
    ocr_lang: str = "eng",
    ocr_backend: str = "tesseract",
    page_workers: int = 1,
    assetless_figure_text: bool = False,
    image_extraction_page_timeout_seconds: float | None = None,
    image_extraction_stage_timeout_seconds: float | None = None,
    figure_semantics_stage_timeout_seconds: float | None = None,
    require_domain_adapter_for_technical_profile: bool = True,
    skip_existing: bool = False,
    warning_limit: int = DEFAULT_WARNING_LIMIT,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Convert one PDF and return artifact links plus structured status."""
    allowed_roots = _allowed_roots(roots)
    resolved_input = ensure_within_roots(input_pdf, allowed_roots, label="input_pdf")
    if output_dir is None:
        resolved_output = default_output_dir_for_input(resolved_input)
        ensure_within_roots(resolved_output, allowed_roots, label="output_dir")
    else:
        resolved_output = ensure_within_roots(output_dir, allowed_roots, label="output_dir")
    config = _build_config(
        input_pdf=resolved_input,
        output_dir=resolved_output,
        rag_profile=rag_profile,
        domain_adapter=domain_adapter,
        manual_domain_adapter_label=manual_domain_adapter_label,
        manual_domain_adapter_keywords=manual_domain_adapter_keywords,
        pages=pages,
        password=password,
        image_mode=image_mode,
        table_mode=table_mode,
        rag_table_output=rag_table_output,
        output_profile=output_profile,
        rag_sidecar_scope=rag_sidecar_scope,
        force_ocr=force_ocr,
        ocr_lang=ocr_lang,
        ocr_backend=ocr_backend,
        page_workers=page_workers,
        assetless_figure_text=assetless_figure_text,
        image_extraction_page_timeout_seconds=image_extraction_page_timeout_seconds,
        image_extraction_stage_timeout_seconds=image_extraction_stage_timeout_seconds,
        figure_semantics_stage_timeout_seconds=figure_semantics_stage_timeout_seconds,
        require_domain_adapter_for_technical_profile=require_domain_adapter_for_technical_profile,
        skip_existing=skip_existing,
    )
    result = run_conversion(config)
    return {
        "schema_version": "1.0",
        "status": result.status.value,
        "exit_code": result.exit_code,
        "output_dir": str(resolved_output),
        "artifact_uris": _artifact_map(resolved_output),
        "markdown_uri": result.markdown_path.resolve().as_uri() if result.markdown_path else None,
        "manifest_uri": result.manifest_path.resolve().as_uri() if result.manifest_path else None,
        "report_uri": result.report_path.resolve().as_uri() if result.report_path else None,
        "warning_count": len(result.warnings),
        "warnings_preview": _warning_preview(result, warning_limit),
        "report_summary": _report_summary(result),
        "options": {
            "rag_profile": rag_profile,
            "domain_adapter": config.domain_adapter,
            "manual_domain_adapter_label": config.manual_domain_adapter_label,
            "manual_domain_adapter_keywords_supplied": manual_domain_adapter_keywords is not None,
            "image_mode": config.image_mode,
            "table_mode": config.table_mode,
            "rag_table_output": config.rag_table_output,
            "output_profile": config.output_profile,
            "rag_sidecar_scope": config.rag_sidecar_scope,
            "assetless_figure_text": assetless_figure_text,
            "image_extraction_page_timeout_seconds": config.image_extraction_page_timeout_seconds,
            "image_extraction_stage_timeout_seconds": config.image_extraction_stage_timeout_seconds,
            "figure_semantics_stage_timeout_seconds": config.figure_semantics_stage_timeout_seconds,
            "password_supplied": password is not None,
        },
    }


def validate_output(
    *,
    output_dir: str,
    target: str = "all",
    confidential_safe: bool = False,
    metadata_max_bytes: int | None = None,
    fail_on_warning: bool = False,
    finding_limit: int = DEFAULT_WARNING_LIMIT,
    roots: list[Path] | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Run local-only output validators and write their reports."""
    if project_root is not None:
        _ensure_project_root_on_path(project_root)
    allowed_roots = _allowed_roots(roots)
    resolved_output = ensure_within_roots(output_dir, allowed_roots, label="output_dir")
    from scripts.validate_artifact_integrity import REPORT_FILENAME as ARTIFACT_REPORT
    from scripts.validate_artifact_integrity import validate_artifact_integrity
    from scripts.validate_index_contract import REPORT_FILENAME as INDEX_REPORT
    from scripts.validate_index_contract import validate_index_contract
    from scripts.validate_provenance_integrity import REPORT_FILENAME as PROVENANCE_REPORT
    from scripts.validate_provenance_integrity import validate_provenance_integrity

    reports = {
        INDEX_REPORT: validate_index_contract(
            output_dir=resolved_output,
            target=target,
            confidential_safe=confidential_safe,
            metadata_max_bytes=metadata_max_bytes,
        ),
        PROVENANCE_REPORT: validate_provenance_integrity(output_dir=resolved_output),
        ARTIFACT_REPORT: validate_artifact_integrity(output_dir=resolved_output, confidential_safe=confidential_safe),
    }
    report_uris: dict[str, str] = {}
    for filename, payload in reports.items():
        path = resolved_output / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_uris[filename] = path.resolve().as_uri()

    report_summaries = {
        filename: {
            "status": payload.get("status"),
            "passed": payload.get("passed"),
            "summary": payload.get("summary", {}),
        }
        for filename, payload in reports.items()
    }
    findings_preview = {
        filename: payload.get("findings", [])[: max(finding_limit, 0)]
        for filename, payload in reports.items()
    }
    error_count = sum(
        int(report["summary"].get("error_count", 0))
        for report in report_summaries.values()
    )
    warning_count = sum(
        int(report["summary"].get("warning_count", 0))
        for report in report_summaries.values()
    )
    passed = error_count == 0 and (warning_count == 0 or not fail_on_warning)
    return {
        "schema_version": "1.0",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "output_dir": str(resolved_output),
        "target": target,
        "confidential_safe": confidential_safe,
        "summary": {
            "error_count": error_count,
            "warning_count": warning_count,
            "fail_on_warning": fail_on_warning,
        },
        "report_summaries": report_summaries,
        "findings_preview": findings_preview,
        "report_uris": report_uris,
    }


def inspect_report(
    *,
    output_dir: str,
    warning_limit: int = DEFAULT_WARNING_LIMIT,
    roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Read report/manifest summaries without returning raw Markdown or PDF text."""
    allowed_roots = _allowed_roots(roots)
    resolved_output = ensure_within_roots(output_dir, allowed_roots, label="output_dir")
    report_path = resolved_output / "report.json"
    manifest_path = resolved_output / "manifest.json"
    report = _read_optional_json(report_path)
    manifest = _read_optional_json(manifest_path)
    warnings = report.get("warnings", []) if isinstance(report, dict) else []
    if not isinstance(warnings, list):
        warnings = []
    return {
        "schema_version": "1.0",
        "output_dir": str(resolved_output),
        "report_uri": report_path.resolve().as_uri() if report_path.exists() else None,
        "manifest_uri": manifest_path.resolve().as_uri() if manifest_path.exists() else None,
        "artifact_uris": _artifact_map(resolved_output),
        "status": report.get("status") if isinstance(report, dict) else None,
        "summary": report.get("summary") if isinstance(report, dict) else None,
        "manifest_options": manifest.get("options") if isinstance(manifest, dict) else None,
        "warnings_preview": warnings[: max(warning_limit, 0)],
        "warning_count": len(warnings),
    }


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def read_repo_resource(relative_path: str, *, project_root: Path | None = None) -> str:
    """Read a committed text resource from the repository root."""
    root = _ensure_project_root_on_path(project_root)
    path = ensure_within_roots(root / relative_path, [root], label=relative_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def build_mcp_server(*, project_root: Path | None = None) -> Any:
    """Build the local stdio MCP server."""
    FastMCP = _require_fastmcp()
    root = _ensure_project_root_on_path(project_root)
    roots = configured_roots(project_root)
    mcp = FastMCP(SERVER_NAME)

    @mcp.tool()
    def pdf2md_doctor(skip_ocr_check: bool = False, ocr_lang: str = "eng") -> dict[str, Any]:
        """Check pdf2md MCP server readiness and optional OCR runtime availability."""
        return doctor(skip_ocr_check=skip_ocr_check, ocr_lang=ocr_lang, roots=roots, project_root=root)

    @mcp.tool()
    def pdf2md_list_profiles() -> dict[str, Any]:
        """List supported pdf2md RAG profiles, adapters, and output modes."""
        return list_profiles()

    @mcp.tool()
    def pdf2md_plan_page_windows(
        input_pdf: str,
        output_dir: str | None = None,
        pages: str | None = None,
        password: str | None = None,
        window_size: int = 100,
    ) -> dict[str, Any]:
        """Plan deterministic page windows for a large PDF conversion."""
        return plan_page_windows(
            input_pdf=input_pdf,
            output_dir=output_dir,
            pages=pages,
            password=password,
            window_size=window_size,
            roots=roots,
        )

    @mcp.tool()
    def pdf2md_convert_page_window(
        input_pdf: str,
        output_dir: str | None = None,
        window_id: str = "",
        pages: str | None = None,
        password: str | None = None,
        window_size: int = 100,
        rag_profile: str = "preserve",
        domain_adapter: str | None = None,
        manual_domain_adapter_label: str | None = None,
        manual_domain_adapter_keywords: str | None = None,
        image_mode: str | None = None,
        table_mode: str | None = None,
        rag_table_output: str | None = None,
        output_profile: str = OutputProfile.FULL.value,
        rag_sidecar_scope: str | None = None,
        force_ocr: bool = False,
        ocr_lang: str = "eng",
        ocr_backend: str = "tesseract",
        page_workers: int = 1,
        assetless_figure_text: bool = False,
        image_extraction_page_timeout_seconds: float | None = None,
        image_extraction_stage_timeout_seconds: float | None = None,
        figure_semantics_stage_timeout_seconds: float | None = None,
        require_domain_adapter_for_technical_profile: bool = True,
        skip_existing: bool = False,
        warning_limit: int = DEFAULT_WARNING_LIMIT,
    ) -> dict[str, Any]:
        """Convert one planned page window into its stable windows/pages-* output directory."""
        if not window_id:
            raise ValueError("window_id is required")
        return convert_page_window(
            input_pdf=input_pdf,
            output_dir=output_dir,
            window_id=window_id,
            pages=pages,
            password=password,
            window_size=window_size,
            rag_profile=rag_profile,
            domain_adapter=domain_adapter,
            manual_domain_adapter_label=manual_domain_adapter_label,
            manual_domain_adapter_keywords=manual_domain_adapter_keywords,
            image_mode=image_mode,
            table_mode=table_mode,
            rag_table_output=rag_table_output,
            output_profile=output_profile,
            rag_sidecar_scope=rag_sidecar_scope,
            force_ocr=force_ocr,
            ocr_lang=ocr_lang,
            ocr_backend=ocr_backend,
            page_workers=page_workers,
            assetless_figure_text=assetless_figure_text,
            image_extraction_page_timeout_seconds=image_extraction_page_timeout_seconds,
            image_extraction_stage_timeout_seconds=image_extraction_stage_timeout_seconds,
            figure_semantics_stage_timeout_seconds=figure_semantics_stage_timeout_seconds,
            require_domain_adapter_for_technical_profile=require_domain_adapter_for_technical_profile,
            skip_existing=skip_existing,
            warning_limit=warning_limit,
            roots=roots,
        )

    @mcp.tool()
    def pdf2md_merge_window_outputs(
        output_dir: str,
        input_pdf: str | None = None,
        pages: str | None = None,
        password: str | None = None,
        window_size: int = 100,
        validate_windows: bool = True,
        validate_merged: bool = True,
    ) -> dict[str, Any]:
        """Merge deterministic page-window outputs into one public output directory."""
        return merge_window_outputs(
            input_pdf=input_pdf,
            output_dir=output_dir,
            pages=pages,
            password=password,
            window_size=window_size,
            validate_windows=validate_windows,
            validate_merged=validate_merged,
            roots=roots,
            project_root=root,
        )

    @mcp.tool()
    def pdf2md_convert_pdf_windowed(
        input_pdf: str,
        output_dir: str | None = None,
        pages: str | None = None,
        password: str | None = None,
        window_size: int = 100,
        rag_profile: str = "preserve",
        domain_adapter: str | None = None,
        manual_domain_adapter_label: str | None = None,
        manual_domain_adapter_keywords: str | None = None,
        image_mode: str | None = None,
        table_mode: str | None = None,
        rag_table_output: str | None = None,
        output_profile: str = OutputProfile.FULL.value,
        rag_sidecar_scope: str | None = None,
        force_ocr: bool = False,
        ocr_lang: str = "eng",
        ocr_backend: str = "tesseract",
        page_workers: int = 1,
        assetless_figure_text: bool = False,
        image_extraction_page_timeout_seconds: float | None = None,
        image_extraction_stage_timeout_seconds: float | None = None,
        figure_semantics_stage_timeout_seconds: float | None = None,
        require_domain_adapter_for_technical_profile: bool = True,
        skip_existing: bool = False,
        validate_windows: bool = True,
        validate_merged: bool = True,
        warning_limit: int = DEFAULT_WARNING_LIMIT,
    ) -> dict[str, Any]:
        """Plan, convert, validate, and merge deterministic page windows for one PDF."""
        return convert_pdf_windowed(
            input_pdf=input_pdf,
            output_dir=output_dir,
            pages=pages,
            password=password,
            window_size=window_size,
            rag_profile=rag_profile,
            domain_adapter=domain_adapter,
            manual_domain_adapter_label=manual_domain_adapter_label,
            manual_domain_adapter_keywords=manual_domain_adapter_keywords,
            image_mode=image_mode,
            table_mode=table_mode,
            rag_table_output=rag_table_output,
            output_profile=output_profile,
            rag_sidecar_scope=rag_sidecar_scope,
            force_ocr=force_ocr,
            ocr_lang=ocr_lang,
            ocr_backend=ocr_backend,
            page_workers=page_workers,
            assetless_figure_text=assetless_figure_text,
            image_extraction_page_timeout_seconds=image_extraction_page_timeout_seconds,
            image_extraction_stage_timeout_seconds=image_extraction_stage_timeout_seconds,
            figure_semantics_stage_timeout_seconds=figure_semantics_stage_timeout_seconds,
            require_domain_adapter_for_technical_profile=require_domain_adapter_for_technical_profile,
            skip_existing=skip_existing,
            validate_windows=validate_windows,
            validate_merged=validate_merged,
            warning_limit=warning_limit,
            roots=roots,
            project_root=root,
        )

    @mcp.tool()
    def pdf2md_convert_pdf(
        input_pdf: str,
        output_dir: str | None = None,
        rag_profile: str = "preserve",
        domain_adapter: str | None = None,
        manual_domain_adapter_label: str | None = None,
        manual_domain_adapter_keywords: str | None = None,
        pages: str | None = None,
        password: str | None = None,
        image_mode: str | None = None,
        table_mode: str | None = None,
        rag_table_output: str | None = None,
        output_profile: str = OutputProfile.FULL.value,
        rag_sidecar_scope: str | None = None,
        force_ocr: bool = False,
        ocr_lang: str = "eng",
        ocr_backend: str = "tesseract",
        page_workers: int = 1,
        assetless_figure_text: bool = False,
        image_extraction_page_timeout_seconds: float | None = None,
        image_extraction_stage_timeout_seconds: float | None = None,
        figure_semantics_stage_timeout_seconds: float | None = None,
        require_domain_adapter_for_technical_profile: bool = True,
        skip_existing: bool = False,
        warning_limit: int = DEFAULT_WARNING_LIMIT,
    ) -> dict[str, Any]:
        """Convert one PDF and return artifact URIs, report status, and warning summary."""
        return convert_pdf(
            input_pdf=input_pdf,
            output_dir=output_dir,
            rag_profile=rag_profile,
            domain_adapter=domain_adapter,
            manual_domain_adapter_label=manual_domain_adapter_label,
            manual_domain_adapter_keywords=manual_domain_adapter_keywords,
            pages=pages,
            password=password,
            image_mode=image_mode,
            table_mode=table_mode,
            rag_table_output=rag_table_output,
            output_profile=output_profile,
            rag_sidecar_scope=rag_sidecar_scope,
            force_ocr=force_ocr,
            ocr_lang=ocr_lang,
            ocr_backend=ocr_backend,
            page_workers=page_workers,
            assetless_figure_text=assetless_figure_text,
            image_extraction_page_timeout_seconds=image_extraction_page_timeout_seconds,
            image_extraction_stage_timeout_seconds=image_extraction_stage_timeout_seconds,
            figure_semantics_stage_timeout_seconds=figure_semantics_stage_timeout_seconds,
            require_domain_adapter_for_technical_profile=require_domain_adapter_for_technical_profile,
            skip_existing=skip_existing,
            warning_limit=warning_limit,
            roots=roots,
        )

    @mcp.tool()
    def pdf2md_validate_output(
        output_dir: str,
        target: str = "all",
        confidential_safe: bool = False,
        metadata_max_bytes: int | None = None,
        fail_on_warning: bool = False,
        finding_limit: int = DEFAULT_WARNING_LIMIT,
    ) -> dict[str, Any]:
        """Run local-only RAG index, provenance, and artifact integrity validators."""
        return validate_output(
            output_dir=output_dir,
            target=target,
            confidential_safe=confidential_safe,
            metadata_max_bytes=metadata_max_bytes,
            fail_on_warning=fail_on_warning,
            finding_limit=finding_limit,
            roots=roots,
            project_root=root,
        )

    @mcp.tool()
    def pdf2md_inspect_report(output_dir: str, warning_limit: int = DEFAULT_WARNING_LIMIT) -> dict[str, Any]:
        """Inspect report.json and manifest.json summaries without returning raw Markdown body."""
        return inspect_report(output_dir=output_dir, warning_limit=warning_limit, roots=roots)

    @mcp.resource("pdf2md://docs/output-schema")
    def output_schema_contract() -> str:
        """Return the committed pdf2md output schema contract."""
        return read_repo_resource("docs/OUTPUT_SCHEMA.md", project_root=root)

    @mcp.resource("pdf2md://docs/rag-indexer-recipes")
    def rag_indexer_recipes() -> str:
        """Return local RAG indexer integration recipes."""
        return read_repo_resource("docs/RAG_INDEXER_INTEGRATION_RECIPES.md", project_root=root)

    @mcp.resource("pdf2md://docs/mcp-server-development-spec")
    def mcp_server_development_spec() -> str:
        """Return the MCP server development specification."""
        return read_repo_resource("docs/MCP_SERVER_DEVELOPMENT_SPEC.md", project_root=root)

    @mcp.prompt()
    def convert_pdf_for_rag(input_pdf: str, output_dir: str, profile: str = "rag_optimized") -> str:
        """Prompt for converting a PDF into RAG-ready pdf2md artifacts."""
        return (
            "Convert the PDF with pdf2md while preserving source text. "
            f"Use pdf2md_convert_pdf(input_pdf={input_pdf!r}, output_dir={output_dir!r}, "
            f"rag_profile={profile!r}), then run pdf2md_validate_output on the output directory. "
            "Summarize status, artifact URIs, and warnings; do not paste the full Markdown body unless requested."
        )

    @mcp.prompt()
    def convert_technical_spec(input_pdf: str, output_dir: str, domain_adapter: str) -> str:
        """Prompt for storage/security technical-spec RAG conversion."""
        return (
            "Convert this technical specification with conservative table and provenance handling. "
            f"Use pdf2md_convert_pdf(input_pdf={input_pdf!r}, output_dir={output_dir!r}, "
            "rag_profile='technical_spec_rag', "
            f"domain_adapter={domain_adapter!r}), then validate the output. "
            "Report domain sidecar availability, table/requirement counts, and actionable warnings only."
        )

    @mcp.prompt()
    def convert_visual_technical_spec(input_pdf: str, output_dir: str, domain_adapter: str) -> str:
        """Prompt for storage/security technical-spec RAG conversion with visual sidecars."""
        return (
            "Convert this technical specification with figure evidence enabled and conservative provenance handling. "
            f"Use pdf2md_convert_pdf(input_pdf={input_pdf!r}, output_dir={output_dir!r}, "
            "rag_profile='technical_spec_rag_visual', "
            f"domain_adapter={domain_adapter!r}), then validate the output. "
            "Report visual sidecar counts, domain sidecar availability, and actionable warnings only."
        )

    @mcp.prompt()
    def triage_conversion_warnings(output_dir: str) -> str:
        """Prompt for summarizing conversion warnings from existing pdf2md artifacts."""
        return (
            f"Use pdf2md_inspect_report(output_dir={output_dir!r}) and group warnings by code/severity. "
            "Explain which warnings are actionable, which are advisory, and which output artifacts should be checked."
        )

    return mcp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local stdio MCP server for pdf2md.")
    parser.add_argument(
        "--transport",
        choices=("stdio",),
        default="stdio",
        help="MCP transport. Only local stdio is implemented; Streamable HTTP is documented for future work.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Repository root for static MCP resources. Defaults to the current working directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        server = build_mcp_server(project_root=args.project_root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
