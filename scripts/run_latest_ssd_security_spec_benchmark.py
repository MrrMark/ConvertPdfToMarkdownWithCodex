#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.config import Config
from pdf2md.models import (
    DomainAdapterMode,
    ImageMode,
    LatestSsdSecuritySpecBenchmarkReport,
    RagTableOutputMode,
    TableMode,
)
from pdf2md.pipeline import run_conversion
from pdf2md.rag_profiles import rag_profile_options
from pdf2md.serializers.rag_domain_adapters import get_domain_adapter_spec
from pdf2md.utils.io import write_json, write_text

try:
    from scripts.validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract  # type: ignore[no-redef]


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "latest_ssd_security_spec_benchmark_report.json"
SCORECARD_FILENAME = "latest_ssd_security_spec_benchmark_scorecard.md"
CONVERSION_OUTPUT_DIRNAME = "conversion"

FULL_PRECISION_MODE = "full_precision"
FAST_SMOKE_MODE = "fast_smoke"
BENCHMARK_MODES = (FULL_PRECISION_MODE, FAST_SMOKE_MODE)
DEFAULT_FAST_SMOKE_PAGES = "1-3"

SPDM_DOCUMENT = "spdm"
SPDM_STORAGE_BINDING_DOCUMENT = "spdm-storage-binding"
TCG_STORAGE_DOCUMENT = "tcg-storage"
PCIE_BASE_DOCUMENT = "pcie-base"
CALIPTRA_DOCUMENT = "caliptra"
SPEC_DOCUMENT_TYPES = (
    SPDM_DOCUMENT,
    SPDM_STORAGE_BINDING_DOCUMENT,
    TCG_STORAGE_DOCUMENT,
    PCIE_BASE_DOCUMENT,
    CALIPTRA_DOCUMENT,
)

SPEC_DOCUMENT_METADATA: dict[str, dict[str, str | None]] = {
    SPDM_DOCUMENT: {
        "latest_spec_set": "DMTF SPDM 1.4.0",
        "latest_release_date": "2025-05-25",
        "expected_spec_title": "Security Protocol and Data Model (SPDM) Specification",
        "expected_revision": "1.4.0",
        "source_url": "https://www.dmtf.org/standards/spdm",
        "domain_adapter": DomainAdapterMode.SPDM.value,
    },
    SPDM_STORAGE_BINDING_DOCUMENT: {
        "latest_spec_set": "DMTF SPDM to Storage Binding 1.0.0",
        "latest_release_date": "2025-05-25",
        "expected_spec_title": "Security Protocol and Data Model (SPDM) to Storage Binding Specification",
        "expected_revision": "1.0.0",
        "source_url": "https://www.dmtf.org/standards/spdm",
        "domain_adapter": DomainAdapterMode.SPDM.value,
    },
    TCG_STORAGE_DOCUMENT: {
        "latest_spec_set": "TCG Storage security specifications",
        "latest_release_date": None,
        "expected_spec_title": "TCG Storage Security Specification",
        "expected_revision": None,
        "source_url": "https://trustedcomputinggroup.org",
        "domain_adapter": DomainAdapterMode.TCG.value,
    },
    PCIE_BASE_DOCUMENT: {
        "latest_spec_set": "PCI Express Base Specification",
        "latest_release_date": None,
        "expected_spec_title": "PCI Express Base Specification",
        "expected_revision": None,
        "source_url": "https://pcisig.com",
        "domain_adapter": DomainAdapterMode.PCIE.value,
    },
    CALIPTRA_DOCUMENT: {
        "latest_spec_set": "Caliptra 2.1",
        "latest_release_date": None,
        "expected_spec_title": "Caliptra: A Datacenter System on a Chip (SoC) Root of Trust (RoT)",
        "expected_revision": "2.1",
        "source_url": "https://spec.caliptra.io/",
        "domain_adapter": DomainAdapterMode.CALIPTRA.value,
    },
}

SIDECAR_FILES = (
    "text_blocks_rag.jsonl",
    "semantic_units_rag.jsonl",
    "requirements_rag.jsonl",
    "cross_refs_rag.jsonl",
    "requirement_traceability_rag.jsonl",
    "technical_tables_rag.jsonl",
    "figures_rag.jsonl",
    "figure_ocr_evidence_rag.jsonl",
    "figure_descriptions_rag.jsonl",
    "figure_structures_rag.jsonl",
    "domain_units_rag.jsonl",
    "page_layout_rag.jsonl",
    "retrieval_chunks_rag.jsonl",
    "tables_rag.jsonl",
    "rag_tables.md",
)


@dataclass(frozen=True)
class LatestSsdSecuritySpecBenchmarkConfig:
    input_pdf: Path
    output_dir: Path
    spec_document_type: str = SPDM_DOCUMENT
    mode: str = FULL_PRECISION_MODE
    source_url: str | None = None
    pages: str | None = None
    page_workers: int = 1
    visual_mode: bool = False
    require_tables: bool = True
    require_domain_units: bool = True


def _spec_metadata(spec_document_type: str) -> dict[str, str | None]:
    return SPEC_DOCUMENT_METADATA.get(spec_document_type, SPEC_DOCUMENT_METADATA[SPDM_DOCUMENT])


def _domain_adapter(spec_document_type: str) -> str:
    return str(_spec_metadata(spec_document_type)["domain_adapter"])


def _source_url(*, spec_document_type: str, source_url: str | None) -> str:
    if source_url:
        return source_url
    return str(_spec_metadata(spec_document_type)["source_url"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    return summary if isinstance(summary, dict) else {}


def _int_value(mapping: dict[str, Any], key: str, default: int = 0) -> int:
    value = mapping.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _effective_pages(mode: str, pages: str | None) -> str | None:
    if pages is not None:
        return pages
    if mode == FAST_SMOKE_MODE:
        return DEFAULT_FAST_SMOKE_PAGES
    return None


def _mode_image_mode(mode: str) -> str:
    if mode == FAST_SMOKE_MODE:
        return ImageMode.PLACEHOLDER.value
    return ImageMode.REFERENCED.value


def build_option_matrix(
    *,
    mode: str,
    pages: str | None,
    page_workers: int,
    spec_document_type: str = SPDM_DOCUMENT,
    visual_mode: bool = False,
    require_tables: bool = True,
    require_domain_units: bool = True,
) -> dict[str, Any]:
    """Return the sanitized option matrix used by the SSD security benchmark conversion."""
    domain_adapter = _domain_adapter(spec_document_type)
    adapter_spec = get_domain_adapter_spec(domain_adapter)
    rag_profile = "technical_spec_rag_visual" if visual_mode else "technical_spec_rag"
    options = rag_profile_options(rag_profile)
    return {
        "spec_document_type": spec_document_type,
        "benchmark_mode": mode,
        "pages": _effective_pages(mode, pages),
        "page_workers": page_workers,
        "visual_mode": visual_mode,
        "rag_profile": rag_profile,
        "domain_adapter": domain_adapter,
        "image_mode": _mode_image_mode(mode),
        "table_mode": TableMode.AUTO.value,
        "rag_table_output": RagTableOutputMode.BOTH.value,
        "keep_page_markers": options.keep_page_markers,
        "remove_header_footer": options.remove_header_footer,
        "repair_hyphenation": options.repair_hyphenation,
        "retrieval_chunk_max_tokens": options.retrieval_chunk_max_tokens,
        "retrieval_tokenizer": options.retrieval_tokenizer,
        "rag_contextual_embedding_text": options.rag_contextual_embedding_text,
        "rag_merge_sibling_text_chunks": options.rag_merge_sibling_text_chunks,
        "rag_chunk_relationship_metadata": options.rag_chunk_relationship_metadata,
        "rag_figure_text_chunks": options.rag_figure_text_chunks,
        "figure_region_ocr": options.figure_region_ocr,
        "rag_generated_figure_descriptions": options.rag_generated_figure_descriptions,
        "figure_description_backend": options.figure_description_backend,
        "figure_structure_extraction": options.figure_structure_extraction,
        "security_unit_taxonomy": list(adapter_spec.unit_taxonomy),
        "contract_validator": {
            "ssd_agent_domain": adapter_spec.ssd_agent_domain,
            "ssd_agent_spec_type": DOMAIN_ADAPTER_TO_SPEC_TYPE[domain_adapter],
            "domain_adapter": domain_adapter,
            "require_tables": require_tables,
            "require_domain_units": require_domain_units,
        },
    }


def build_conversion_config(
    *,
    config: LatestSsdSecuritySpecBenchmarkConfig,
    conversion_output_dir: Path,
) -> Config:
    """Build the deterministic technical-spec RAG conversion config for the SSD security benchmark."""
    matrix = build_option_matrix(
        mode=config.mode,
        pages=config.pages,
        page_workers=config.page_workers,
        spec_document_type=config.spec_document_type,
        visual_mode=config.visual_mode,
        require_tables=config.require_tables,
        require_domain_units=config.require_domain_units,
    )
    return Config(
        input_pdf=config.input_pdf,
        output_dir=conversion_output_dir,
        pages=matrix["pages"],
        image_mode=matrix["image_mode"],
        table_mode=matrix["table_mode"],
        rag_table_output=matrix["rag_table_output"],
        rag_profile=matrix["rag_profile"],
        domain_adapter=matrix["domain_adapter"],
        keep_page_markers=matrix["keep_page_markers"],
        remove_header_footer=matrix["remove_header_footer"],
        repair_hyphenation=matrix["repair_hyphenation"],
        retrieval_chunk_max_tokens=matrix["retrieval_chunk_max_tokens"],
        retrieval_tokenizer=matrix["retrieval_tokenizer"],
        rag_contextual_embedding_text=matrix["rag_contextual_embedding_text"],
        rag_merge_sibling_text_chunks=matrix["rag_merge_sibling_text_chunks"],
        rag_chunk_relationship_metadata=matrix["rag_chunk_relationship_metadata"],
        rag_figure_text_chunks=matrix["rag_figure_text_chunks"],
        figure_region_ocr=matrix["figure_region_ocr"],
        rag_generated_figure_descriptions=matrix["rag_generated_figure_descriptions"],
        figure_description_backend=matrix["figure_description_backend"],
        figure_structure_extraction=matrix["figure_structure_extraction"],
        page_workers=config.page_workers,
    )


def collect_sidecar_summary(output_dir: Path) -> dict[str, Any]:
    """Collect sidecar sizes and line counts without embedding raw sidecar content."""
    files: dict[str, dict[str, int | bool]] = {}
    for filename in SIDECAR_FILES:
        path = output_dir / filename
        files[filename] = {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "record_count": _read_jsonl_count(path) if filename.endswith(".jsonl") else 0,
        }
    return {
        "files": files,
        "file_count": sum(1 for record in files.values() if record["exists"]),
        "total_bytes": sum(int(record["bytes"]) for record in files.values()),
    }


def _contract_summary(
    output_dir: Path,
    *,
    source_sha256: str,
    domain_adapter: str,
    require_tables: bool,
    require_domain_units: bool,
) -> dict[str, Any]:
    adapter_spec = get_domain_adapter_spec(domain_adapter)
    try:
        report = validate_ssd_rag_contract(
            output_dir=output_dir,
            ssd_agent_domain=adapter_spec.ssd_agent_domain,
            ssd_agent_spec_type=DOMAIN_ADAPTER_TO_SPEC_TYPE[domain_adapter],
            domain_adapter=domain_adapter,
            source_sha256=source_sha256,
            require_tables=require_tables,
            require_domain_units=require_domain_units,
        )
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        return {
            "status": "failed",
            "passed": False,
            "summary": {"error_count": 1, "warning_count": 0, "exception_type": type(exc).__name__},
        }
    summary = _summary(report)
    return {
        "status": "passed" if report.get("passed") is True else "failed",
        "passed": report.get("passed") is True,
        "summary": {
            "chunk_count": _int_value(summary, "chunk_count"),
            "mapped_chunk_count": _int_value(summary, "mapped_chunk_count"),
            "table_row_count": _int_value(summary, "table_row_count"),
            "technical_table_row_count": _int_value(summary, "technical_table_row_count"),
            "domain_unit_count": _int_value(summary, "domain_unit_count"),
            "requirement_traceability_count": _int_value(summary, "requirement_traceability_count"),
            "error_count": _int_value(summary, "error_count"),
            "warning_count": _int_value(summary, "warning_count"),
        },
    }


def _domain_unit_type_counts(output_dir: Path, *, domain_adapter: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in _read_jsonl_records(output_dir / "domain_units_rag.jsonl"):
        if record.get("domain") != domain_adapter:
            continue
        unit_type = str(record.get("unit_type") or "unknown")
        counts[unit_type] = counts.get(unit_type, 0) + 1
    return dict(sorted(counts.items()))


def _summary_counts(
    *,
    manifest: dict[str, Any],
    conversion_report: dict[str, Any],
    sidecars: dict[str, Any],
    contract: dict[str, Any],
    output_dir: Path,
    domain_adapter: str,
) -> dict[str, Any]:
    conversion_summary = _summary(conversion_report)
    contract_summary = _summary(contract)
    page_count = _int_value(conversion_summary, "processed_pages")
    if page_count == 0 and isinstance(manifest.get("selected_pages"), list):
        page_count = len(manifest["selected_pages"])
    conversion_error_count = 1 if str(conversion_report.get("status") or "") == "failed" else 0
    contract_error_count = _int_value(contract_summary, "error_count")
    conversion_warning_count = _int_value(conversion_summary, "warning_count")
    contract_warning_count = _int_value(contract_summary, "warning_count")
    return {
        "page_count": page_count,
        "conversion_duration_ms": conversion_report.get("duration_ms"),
        "sidecar_file_count": sidecars["file_count"],
        "sidecar_total_bytes": sidecars["total_bytes"],
        "sidecar_file_sizes": {
            filename: int(record["bytes"])
            for filename, record in sidecars["files"].items()
            if isinstance(record, dict) and record.get("exists")
        },
        "retrieval_chunk_count": _int_value(conversion_summary, "retrieval_chunk_record_count"),
        "requirement_count": _int_value(conversion_summary, "requirement_record_count"),
        "traceability_record_count": _int_value(conversion_summary, "requirement_traceability_record_count"),
        "technical_table_unit_count": _int_value(conversion_summary, "technical_table_record_count"),
        "domain_unit_count": _int_value(conversion_summary, "domain_unit_record_count"),
        "security_domain_unit_counts": _domain_unit_type_counts(output_dir, domain_adapter=domain_adapter),
        "figure_rag_record_count": _int_value(conversion_summary, "figure_rag_record_count"),
        "figure_text_chunk_record_count": _int_value(conversion_summary, "figure_text_chunk_record_count"),
        "figure_description_record_count": _int_value(conversion_summary, "figure_description_record_count"),
        "figure_description_chunk_record_count": _int_value(
            conversion_summary,
            "figure_description_chunk_record_count",
        ),
        "figure_structure_record_count": _int_value(conversion_summary, "figure_structure_record_count"),
        "figure_structure_chunk_record_count": _int_value(conversion_summary, "figure_structure_chunk_record_count"),
        "figure_region_ocr_attempted_count": _int_value(conversion_summary, "figure_region_ocr_attempted_count"),
        "figure_region_ocr_promoted_label_count": _int_value(
            conversion_summary,
            "figure_region_ocr_promoted_label_count",
        ),
        "figure_region_ocr_runtime_unavailable_count": _int_value(
            conversion_summary,
            "figure_region_ocr_runtime_unavailable_count",
        ),
        "figure_ocr_evidence_record_count": _int_value(conversion_summary, "figure_ocr_evidence_record_count"),
        "contract_validation_status": contract.get("status"),
        "contract_validation_passed": contract.get("passed") is True,
        "warning_count": conversion_warning_count + contract_warning_count,
        "error_count": conversion_error_count + contract_error_count,
        "conversion_warning_count": conversion_warning_count,
        "contract_warning_count": contract_warning_count,
        "conversion_error_count": conversion_error_count,
        "contract_error_count": contract_error_count,
    }


def render_scorecard(report: dict[str, Any]) -> str:
    counts = report.get("summary_counts", {})
    unit_counts = counts.get("security_domain_unit_counts")
    unit_counts = unit_counts if isinstance(unit_counts, dict) else {}
    lines = [
        "# Latest SSD Security Spec Benchmark Scorecard",
        "",
        f"- Spec document type: `{report.get('spec_document_type')}`",
        f"- Latest spec set: `{report.get('latest_spec_set')}`",
        f"- Latest release date: `{report.get('latest_release_date')}`",
        f"- Expected spec: `{report.get('expected_spec_title')}`",
        f"- Expected revision: `{report.get('expected_revision')}`",
        f"- Source URL: <{report.get('source_url')}>",
        f"- Mode: `{report.get('mode')}`",
        f"- Domain adapter: `{report.get('option_matrix', {}).get('domain_adapter')}`",
        f"- Source SHA-256: `{report.get('source_sha256')}`",
        "- Raw PDF text, raw Markdown body, retrieved text, table row content, image bytes, and local input paths "
        "are not embedded.",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| page_count | {counts.get('page_count', 0)} |",
        f"| conversion_duration_ms | {counts.get('conversion_duration_ms')} |",
        f"| sidecar_total_bytes | {counts.get('sidecar_total_bytes', 0)} |",
        f"| retrieval_chunk_count | {counts.get('retrieval_chunk_count', 0)} |",
        f"| requirement_count | {counts.get('requirement_count', 0)} |",
        f"| traceability_record_count | {counts.get('traceability_record_count', 0)} |",
        f"| technical_table_unit_count | {counts.get('technical_table_unit_count', 0)} |",
        f"| domain_unit_count | {counts.get('domain_unit_count', 0)} |",
        f"| figure_rag_record_count | {counts.get('figure_rag_record_count', 0)} |",
        f"| figure_text_chunk_record_count | {counts.get('figure_text_chunk_record_count', 0)} |",
        f"| figure_description_record_count | {counts.get('figure_description_record_count', 0)} |",
        f"| figure_structure_record_count | {counts.get('figure_structure_record_count', 0)} |",
        f"| figure_region_ocr_attempted_count | {counts.get('figure_region_ocr_attempted_count', 0)} |",
        f"| figure_region_ocr_promoted_label_count | {counts.get('figure_region_ocr_promoted_label_count', 0)} |",
        "| figure_region_ocr_runtime_unavailable_count | "
        f"{counts.get('figure_region_ocr_runtime_unavailable_count', 0)} |",
        f"| figure_ocr_evidence_record_count | {counts.get('figure_ocr_evidence_record_count', 0)} |",
        f"| contract_validation_status | {counts.get('contract_validation_status')} |",
        f"| contract_validation_passed | {counts.get('contract_validation_passed')} |",
        f"| warning_count | {counts.get('warning_count', 0)} |",
        f"| error_count | {counts.get('error_count', 0)} |",
    ]
    if unit_counts:
        lines.extend(["", "## Security Domain Unit Counts", "", "| Unit type | Count |", "| --- | ---: |"])
        lines.extend(f"| {unit_type} | {count} |" for unit_type, count in sorted(unit_counts.items()))
    lines.append("")
    return "\n".join(lines)


def run_latest_ssd_security_spec_benchmark(config: LatestSsdSecuritySpecBenchmarkConfig) -> dict[str, Any]:
    """Run the latest SSD security spec benchmark and return sanitized metrics."""
    metadata = _spec_metadata(config.spec_document_type)
    source_sha256 = _sha256(config.input_pdf)
    conversion_output_dir = config.output_dir / CONVERSION_OUTPUT_DIRNAME
    conversion_config = build_conversion_config(config=config, conversion_output_dir=conversion_output_dir)
    result = run_conversion(conversion_config)
    manifest = _read_json(conversion_output_dir / "manifest.json")
    conversion_report = _read_json(conversion_output_dir / "report.json")
    sidecars = collect_sidecar_summary(conversion_output_dir)
    domain_adapter = _domain_adapter(config.spec_document_type)
    contract = _contract_summary(
        conversion_output_dir,
        source_sha256=source_sha256,
        domain_adapter=domain_adapter,
        require_tables=config.require_tables,
        require_domain_units=config.require_domain_units,
    )
    option_matrix = build_option_matrix(
        mode=config.mode,
        pages=config.pages,
        page_workers=config.page_workers,
        spec_document_type=config.spec_document_type,
        visual_mode=config.visual_mode,
        require_tables=config.require_tables,
        require_domain_units=config.require_domain_units,
    )
    report = LatestSsdSecuritySpecBenchmarkReport(
        schema_version=SCHEMA_VERSION,
        purpose="latest_ssd_security_spec_benchmark",
        spec_document_type=config.spec_document_type,
        latest_spec_set=str(metadata["latest_spec_set"]),
        latest_release_date=metadata["latest_release_date"],
        expected_spec_title=str(metadata["expected_spec_title"]),
        expected_revision=metadata["expected_revision"],
        source_url=_source_url(spec_document_type=config.spec_document_type, source_url=config.source_url),
        source_sha256=source_sha256,
        mode=config.mode,
        option_matrix=option_matrix,
        conversion_exit_code=result.exit_code,
        conversion_status=str(result.status.value if hasattr(result.status, "value") else result.status),
        summary_counts=_summary_counts(
            manifest=manifest,
            conversion_report=conversion_report,
            sidecars=sidecars,
            contract=contract,
            output_dir=conversion_output_dir,
            domain_adapter=domain_adapter,
        ),
        sidecars=sidecars,
        contract_validation=contract,
    ).model_dump(mode="json")
    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(config.output_dir / REPORT_FILENAME, report)
    write_text(config.output_dir / SCORECARD_FILENAME, render_scorecard(report))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a sanitized latest SSD security spec benchmark.")
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--spec-document-type", choices=SPEC_DOCUMENT_TYPES, default=SPDM_DOCUMENT)
    parser.add_argument("--mode", choices=BENCHMARK_MODES, default=FULL_PRECISION_MODE)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--pages", default=None)
    parser.add_argument("--page-workers", type=int, default=1)
    parser.add_argument("--visual-mode", action="store_true")
    parser.add_argument("--no-require-tables", action="store_true")
    parser.add_argument("--no-require-domain-units", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_latest_ssd_security_spec_benchmark(
        LatestSsdSecuritySpecBenchmarkConfig(
            input_pdf=args.input_pdf,
            output_dir=args.output_dir,
            spec_document_type=args.spec_document_type,
            mode=args.mode,
            source_url=args.source_url,
            pages=args.pages,
            page_workers=args.page_workers,
            visual_mode=args.visual_mode,
            require_tables=not args.no_require_tables,
            require_domain_units=not args.no_require_domain_units,
        )
    )
    counts = report["summary_counts"]
    print(
        "Latest SSD security spec benchmark: "
        f"status={report['conversion_status']} contract={counts['contract_validation_status']} "
        f"report={args.output_dir / REPORT_FILENAME}"
    )
    if args.fail_on_error and (counts["error_count"] or report["conversion_exit_code"] != 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
