from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
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
ARTIFACT_FILENAMES = (
    "document.md",
    "manifest.json",
    "report.json",
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
    allowed_roots = roots or configured_roots()
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
    allowed_roots = roots or configured_roots()
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
    allowed_roots = roots or configured_roots()
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
    allowed_roots = roots or configured_roots()
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
    allowed_roots = roots or configured_roots()
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
