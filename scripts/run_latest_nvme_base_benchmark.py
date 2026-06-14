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
    LatestNvmeSpecBenchmarkReport,
    RagTableOutputMode,
    TableMode,
)
from pdf2md.pipeline import run_conversion
from pdf2md.rag_profiles import rag_profile_options
from pdf2md.utils.io import write_json, write_text

try:
    from scripts.validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract  # type: ignore[no-redef]

try:
    from scripts.run_rag_eval import evaluate_queries
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from run_rag_eval import evaluate_queries  # type: ignore[no-redef]

try:
    from scripts.visual_rag_eval import evaluate_visual_chunks
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from visual_rag_eval import evaluate_visual_chunks  # type: ignore[no-redef]


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "latest_nvme_spec_benchmark_report.json"
SCORECARD_FILENAME = "latest_nvme_spec_benchmark_scorecard.md"
CONVERSION_OUTPUT_DIRNAME = "conversion"

FULL_PRECISION_MODE = "full_precision"
FAST_SMOKE_MODE = "fast_smoke"
BENCHMARK_MODES = (FULL_PRECISION_MODE, FAST_SMOKE_MODE)
DEFAULT_FAST_SMOKE_PAGES = "1-5"

OFFICIAL_SOURCE_URL = "https://nvmexpress.org/specifications/"
NVM_COMMAND_SET_SOURCE_URL = (
    "https://nvmexpress.org/wp-content/uploads/"
    "NVM-Express-NVM-Command-Set-Specification-Revision-1.2-2025.08.01-Ratified.pdf"
)
LATEST_NVME_SPEC_SET = "NVMe 2.3"
LATEST_RELEASE_DATE = "2025-08-05"
BASE_SPEC_DOCUMENT = "base"
NVM_COMMAND_SET_SPEC_DOCUMENT = "nvm_command_set"
SPEC_DOCUMENT_TYPES = (BASE_SPEC_DOCUMENT, NVM_COMMAND_SET_SPEC_DOCUMENT)
SPEC_DOCUMENT_METADATA = {
    BASE_SPEC_DOCUMENT: {
        "expected_spec_title": "NVM Express Base Specification",
        "expected_revision": "2.3",
        "source_url": OFFICIAL_SOURCE_URL,
    },
    NVM_COMMAND_SET_SPEC_DOCUMENT: {
        "expected_spec_title": "NVM Express NVM Command Set Specification",
        "expected_revision": "1.2",
        "source_url": NVM_COMMAND_SET_SOURCE_URL,
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
    "figure_descriptions_rag.jsonl",
    "figure_structures_rag.jsonl",
    "domain_units_rag.jsonl",
    "retrieval_chunks_rag.jsonl",
    "tables_rag.jsonl",
    "rag_tables.md",
)

COMMAND_SET_EVAL_PROFILE = "nvme_command_set_p2_retrieval"
COMMAND_SET_EVAL_TOP_K = 5
VISUAL_EVAL_PROFILE = "technical_spec_visual_p3_retrieval"
VISUAL_EVAL_TOP_K = 5
COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES = (
    "command_opcode",
    "command_dword_field",
    "command_pointer_field",
    "status_code",
)


@dataclass(frozen=True)
class LatestNvmeSpecBenchmarkConfig:
    input_pdf: Path
    output_dir: Path
    spec_document_type: str = BASE_SPEC_DOCUMENT
    mode: str = FULL_PRECISION_MODE
    source_url: str | None = None
    pages: str | None = None
    page_workers: int = 1
    visual_mode: bool = False


LatestNvmeBaseBenchmarkConfig = LatestNvmeSpecBenchmarkConfig


def _spec_metadata(spec_document_type: str) -> dict[str, str]:
    return SPEC_DOCUMENT_METADATA.get(spec_document_type, SPEC_DOCUMENT_METADATA[BASE_SPEC_DOCUMENT])


def _source_url(*, spec_document_type: str, source_url: str | None) -> str:
    if source_url:
        return source_url
    return _spec_metadata(spec_document_type)["source_url"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    return {}


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


def _float_value(mapping: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = mapping.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


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
    spec_document_type: str = BASE_SPEC_DOCUMENT,
    visual_mode: bool = False,
) -> dict[str, Any]:
    """Return the sanitized option matrix used by the benchmark conversion."""
    rag_profile = "technical_spec_rag_visual" if visual_mode else "technical_spec_rag"
    options = rag_profile_options(rag_profile)
    return {
        "spec_document_type": spec_document_type,
        "benchmark_mode": mode,
        "pages": _effective_pages(mode, pages),
        "page_workers": page_workers,
        "visual_mode": visual_mode,
        "rag_profile": rag_profile,
        "domain_adapter": DomainAdapterMode.NVME.value,
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
        "command_set_query_eval": {
            "enabled": spec_document_type == NVM_COMMAND_SET_SPEC_DOCUMENT,
            "profile": COMMAND_SET_EVAL_PROFILE,
            "top_k": COMMAND_SET_EVAL_TOP_K,
            "required_unit_types": list(COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES),
            "report_policy": "sanitized_metrics_only",
        },
        "contract_validator": {
            "ssd_agent_domain": "HIL",
            "ssd_agent_spec_type": DOMAIN_ADAPTER_TO_SPEC_TYPE[DomainAdapterMode.NVME.value],
            "domain_adapter": DomainAdapterMode.NVME.value,
            "require_tables": True,
            "require_domain_units": True,
        },
    }


def build_conversion_config(*, config: LatestNvmeSpecBenchmarkConfig, conversion_output_dir: Path) -> Config:
    """Build the deterministic technical-spec RAG conversion config for the benchmark mode."""
    matrix = build_option_matrix(
        mode=config.mode,
        pages=config.pages,
        page_workers=config.page_workers,
        spec_document_type=config.spec_document_type,
        visual_mode=config.visual_mode,
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
    """Collect sidecar sizes and line counts without reading raw record content into the report."""
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


def _contract_summary(output_dir: Path, *, source_sha256: str) -> dict[str, Any]:
    try:
        report = validate_ssd_rag_contract(
            output_dir=output_dir,
            ssd_agent_domain="HIL",
            ssd_agent_spec_type=DOMAIN_ADAPTER_TO_SPEC_TYPE[DomainAdapterMode.NVME.value],
            domain_adapter=DomainAdapterMode.NVME.value,
            source_sha256=source_sha256,
            require_tables=True,
            require_domain_units=True,
        )
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        return {
            "status": "failed",
            "passed": False,
            "summary": {
                "error_count": 1,
                "warning_count": 0,
                "exception_type": type(exc).__name__,
            },
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


def _text_value(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _command_set_query_text(record: dict[str, Any]) -> str:
    unit_type = str(record.get("unit_type") or "")
    fixed_terms = {
        "command_opcode": ("command opcode",),
        "command_dword_field": ("command dword", "cdw"),
        "command_pointer_field": ("command pointer",),
        "status_code": ("status code",),
    }.get(unit_type, (unit_type.replace("_", " "),))
    dynamic_terms = [
        _text_value(record, "command_context", "command"),
        _text_value(record, "opcode"),
        _text_value(record, "command_dword"),
        _text_value(record, "field_name"),
        _text_value(record, "pointer_type"),
        _text_value(record, "status_code_type"),
        _text_value(record, "status_code_value"),
        _text_value(record, "status_code_group"),
        _text_value(record, "error_class"),
        _text_value(record, "retry_hint"),
        _text_value(record, "meaning"),
    ]
    return " ".join(term for term in (*fixed_terms, *dynamic_terms) if term)


def _command_set_eval_queries(
    technical_tables: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    by_unit_type: dict[str, dict[str, Any]] = {}
    for record in technical_tables:
        unit_type = str(record.get("unit_type") or "")
        if unit_type in COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES and unit_type not in by_unit_type:
            by_unit_type[unit_type] = record

    queries: list[dict[str, Any]] = []
    covered_unit_types: list[str] = []
    for unit_type in COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES:
        record = by_unit_type.get(unit_type)
        source_id = _text_value(record or {}, "technical_table_unit_id")
        if record is None or source_id is None:
            continue
        queries.append(
            {
                "query": _command_set_query_text(record),
                "expected_source_ids": [source_id],
                "expected_source_types": ["technical_table_unit"],
                "expected_table_field_source_ids": [source_id],
                "expected_table_field_source_types": ["technical_table_unit"],
            }
        )
        covered_unit_types.append(unit_type)
    missing_unit_types = [unit_type for unit_type in COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES if unit_type not in by_unit_type]
    return queries, covered_unit_types, missing_unit_types


def _command_set_eval_summary(*, output_dir: Path, spec_document_type: str) -> dict[str, Any]:
    if spec_document_type != NVM_COMMAND_SET_SPEC_DOCUMENT:
        return {
            "status": "not_applicable",
            "passed": True,
            "profile": COMMAND_SET_EVAL_PROFILE,
            "top_k": COMMAND_SET_EVAL_TOP_K,
            "query_count": 0,
            "required_unit_types": list(COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES),
            "covered_unit_types": [],
            "missing_unit_types": [],
            "metrics": {
                "hit_at_k": 0.0,
                "mrr": 0.0,
                "expected_source_coverage": 0.0,
                "table_field_coverage": 0.0,
            },
            "raw_content_included": False,
            "queries_included": False,
            "retrieved_text_included": False,
        }

    try:
        technical_tables = _read_jsonl_records(output_dir / "technical_tables_rag.jsonl")
        retrieval_chunks = _read_jsonl_records(output_dir / "retrieval_chunks_rag.jsonl")
        queries, covered_unit_types, missing_unit_types = _command_set_eval_queries(technical_tables)
        if not retrieval_chunks or not queries:
            return {
                "status": "failed",
                "passed": False,
                "profile": COMMAND_SET_EVAL_PROFILE,
                "top_k": COMMAND_SET_EVAL_TOP_K,
                "query_count": len(queries),
                "required_unit_types": list(COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES),
                "covered_unit_types": covered_unit_types,
                "missing_unit_types": missing_unit_types,
                "metrics": {
                    "hit_at_k": 0.0,
                    "mrr": 0.0,
                    "expected_source_coverage": 0.0,
                    "table_field_coverage": 0.0,
                },
                "raw_content_included": False,
                "queries_included": False,
                "retrieved_text_included": False,
            }

        eval_report = evaluate_queries(chunks=retrieval_chunks, queries=queries, top_k=COMMAND_SET_EVAL_TOP_K)
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        return {
            "status": "failed",
            "passed": False,
            "profile": COMMAND_SET_EVAL_PROFILE,
            "top_k": COMMAND_SET_EVAL_TOP_K,
            "query_count": 0,
            "required_unit_types": list(COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES),
            "covered_unit_types": [],
            "missing_unit_types": list(COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES),
            "metrics": {
                "hit_at_k": 0.0,
                "mrr": 0.0,
                "expected_source_coverage": 0.0,
                "table_field_coverage": 0.0,
            },
            "failure_type": type(exc).__name__,
            "raw_content_included": False,
            "queries_included": False,
            "retrieved_text_included": False,
        }

    metrics = eval_report.get("metrics") if isinstance(eval_report.get("metrics"), dict) else {}
    sanitized_metrics = {
        "hit_at_k": _float_value(metrics, "hit_at_k"),
        "mrr": _float_value(metrics, "mrr"),
        "expected_source_coverage": _float_value(metrics, "expected_source_coverage"),
        "expected_source_hit_count": _int_value(metrics, "expected_source_hit_count"),
        "expected_source_total_count": _int_value(metrics, "expected_source_total_count"),
        "expected_source_miss_count": _int_value(metrics, "expected_source_miss_count"),
        "table_field_coverage": _float_value(metrics, "table_field_coverage"),
        "table_contextual_embedding_coverage": _float_value(metrics, "table_contextual_embedding_coverage"),
        "relationship_target_coverage": _float_value(metrics, "relationship_target_coverage", 1.0),
    }
    passed = (
        not missing_unit_types
        and sanitized_metrics["hit_at_k"] >= 1.0
        and sanitized_metrics["expected_source_coverage"] >= 1.0
        and sanitized_metrics["table_field_coverage"] >= 1.0
    )
    return {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "profile": COMMAND_SET_EVAL_PROFILE,
        "top_k": COMMAND_SET_EVAL_TOP_K,
        "query_count": len(queries),
        "required_unit_types": list(COMMAND_SET_EVAL_REQUIRED_UNIT_TYPES),
        "covered_unit_types": covered_unit_types,
        "missing_unit_types": missing_unit_types,
        "metrics": sanitized_metrics,
        "raw_content_included": False,
        "queries_included": False,
        "retrieved_text_included": False,
    }


def _summary_counts(
    *,
    manifest: dict[str, Any],
    conversion_report: dict[str, Any],
    sidecars: dict[str, Any],
    contract: dict[str, Any],
    command_set_eval: dict[str, Any],
    visual_eval: dict[str, Any],
) -> dict[str, Any]:
    conversion_summary = _summary(conversion_report)
    contract_summary = _summary(contract)
    command_eval_metrics = command_set_eval.get("metrics")
    command_eval_metrics = command_eval_metrics if isinstance(command_eval_metrics, dict) else {}
    visual_eval_metrics = visual_eval.get("metrics")
    visual_eval_metrics = visual_eval_metrics if isinstance(visual_eval_metrics, dict) else {}
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
        "visual_eval_status": visual_eval.get("status", "not_applicable"),
        "visual_eval_passed": visual_eval.get("passed") is True,
        "visual_eval_query_count": _int_value(visual_eval, "query_count"),
        "visual_eval_hit_at_k": _float_value(visual_eval_metrics, "hit_at_k"),
        "visual_eval_expected_source_coverage": _float_value(visual_eval_metrics, "expected_source_coverage"),
        "visual_eval_figure_source_ref_coverage": _float_value(
            visual_eval_metrics,
            "figure_source_ref_coverage",
        ),
        "contract_validation_status": contract.get("status"),
        "contract_validation_passed": contract.get("passed") is True,
        "command_set_eval_status": command_set_eval.get("status"),
        "command_set_eval_passed": command_set_eval.get("passed") is True,
        "command_set_eval_query_count": _int_value(command_set_eval, "query_count"),
        "command_set_eval_expected_source_coverage": _float_value(
            command_eval_metrics,
            "expected_source_coverage",
        ),
        "warning_count": conversion_warning_count + contract_warning_count,
        "error_count": conversion_error_count + contract_error_count,
        "conversion_warning_count": conversion_warning_count,
        "contract_warning_count": contract_warning_count,
        "conversion_error_count": conversion_error_count,
        "contract_error_count": contract_error_count,
    }


def render_scorecard(report: dict[str, Any]) -> str:
    counts = report.get("summary_counts", {})
    lines = [
        "# Latest NVMe Spec Benchmark Scorecard",
        "",
        f"- Spec document type: `{report.get('spec_document_type')}`",
        f"- Expected spec: `{report.get('expected_spec_title')}`",
        f"- Expected revision: `{report.get('expected_revision')}`",
        f"- Latest NVMe spec set: `{report.get('latest_spec_set')}` ({report.get('latest_release_date')})",
        f"- Source URL: <{report.get('source_url')}>",
        f"- Mode: `{report.get('mode')}`",
        f"- Source SHA-256: `{report.get('source_sha256')}`",
        "- Raw PDF text, raw Markdown body, generated queries, retrieved text, image bytes, and local input paths "
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
        f"| figure_description_chunk_record_count | {counts.get('figure_description_chunk_record_count', 0)} |",
        f"| figure_structure_record_count | {counts.get('figure_structure_record_count', 0)} |",
        f"| figure_structure_chunk_record_count | {counts.get('figure_structure_chunk_record_count', 0)} |",
        f"| figure_region_ocr_attempted_count | {counts.get('figure_region_ocr_attempted_count', 0)} |",
        f"| figure_region_ocr_promoted_label_count | {counts.get('figure_region_ocr_promoted_label_count', 0)} |",
        "| figure_region_ocr_runtime_unavailable_count | "
        f"{counts.get('figure_region_ocr_runtime_unavailable_count', 0)} |",
        f"| visual_eval_status | {counts.get('visual_eval_status')} |",
        f"| visual_eval_passed | {counts.get('visual_eval_passed')} |",
        f"| visual_eval_query_count | {counts.get('visual_eval_query_count', 0)} |",
        f"| visual_eval_hit_at_k | {counts.get('visual_eval_hit_at_k', 0.0)} |",
        "| visual_eval_expected_source_coverage | "
        f"{counts.get('visual_eval_expected_source_coverage', 0.0)} |",
        "| visual_eval_figure_source_ref_coverage | "
        f"{counts.get('visual_eval_figure_source_ref_coverage', 0.0)} |",
        f"| contract_validation_passed | {counts.get('contract_validation_passed')} |",
        f"| command_set_eval_status | {counts.get('command_set_eval_status')} |",
        f"| command_set_eval_passed | {counts.get('command_set_eval_passed')} |",
        f"| command_set_eval_query_count | {counts.get('command_set_eval_query_count', 0)} |",
        "| command_set_eval_expected_source_coverage | "
        f"{counts.get('command_set_eval_expected_source_coverage', 0.0)} |",
        f"| warning_count | {counts.get('warning_count', 0)} |",
        f"| error_count | {counts.get('error_count', 0)} |",
    ]
    return "\n".join(lines) + "\n"


def run_latest_nvme_spec_benchmark(config: LatestNvmeSpecBenchmarkConfig) -> dict[str, Any]:
    """Run a latest-NVMe technical RAG benchmark and write sanitized reports."""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    conversion_output_dir = config.output_dir / CONVERSION_OUTPUT_DIRNAME
    source_sha256 = _sha256(config.input_pdf)
    conversion_config = build_conversion_config(config=config, conversion_output_dir=conversion_output_dir)
    try:
        result = run_conversion(conversion_config)
        exit_code = result.exit_code
        conversion_report = _as_dict(result.report) or _read_json(conversion_output_dir / "report.json")
    except Exception:  # pragma: no cover - defensive runner boundary
        conversion_output_dir.mkdir(parents=True, exist_ok=True)
        exit_code = 1
        conversion_report = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed",
            "duration_ms": None,
            "summary": {"processed_pages": 0, "warning_count": 0},
        }
    manifest = _read_json(conversion_output_dir / "manifest.json")
    sidecars = collect_sidecar_summary(conversion_output_dir)
    contract = _contract_summary(conversion_output_dir, source_sha256=source_sha256)
    command_set_eval = _command_set_eval_summary(
        output_dir=conversion_output_dir,
        spec_document_type=config.spec_document_type,
    )
    visual_eval = (
        evaluate_visual_chunks(output_dir=conversion_output_dir, profile=VISUAL_EVAL_PROFILE, top_k=VISUAL_EVAL_TOP_K)
        if config.visual_mode
        else {
            "status": "not_applicable",
            "passed": True,
            "profile": VISUAL_EVAL_PROFILE,
            "top_k": VISUAL_EVAL_TOP_K,
            "query_count": 0,
            "metrics": {
                "hit_at_k": 0.0,
                "expected_source_coverage": 0.0,
                "figure_source_ref_coverage": 0.0,
            },
            "queries_included": False,
            "retrieved_text_included": False,
            "raw_content_included": False,
        }
    )
    metadata = _spec_metadata(config.spec_document_type)
    report_payload = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "latest_nvme_spec_benchmark",
        "spec_document_type": config.spec_document_type,
        "latest_spec_set": LATEST_NVME_SPEC_SET,
        "latest_release_date": LATEST_RELEASE_DATE,
        "expected_spec_title": metadata["expected_spec_title"],
        "expected_revision": metadata["expected_revision"],
        "source_url": _source_url(spec_document_type=config.spec_document_type, source_url=config.source_url),
        "source_sha256": source_sha256,
        "mode": config.mode,
        "option_matrix": build_option_matrix(
            mode=config.mode,
            pages=config.pages,
            page_workers=config.page_workers,
            spec_document_type=config.spec_document_type,
            visual_mode=config.visual_mode,
        ),
        "conversion_exit_code": exit_code,
        "conversion_status": str(conversion_report.get("status") or ""),
        "conversion_output_label": CONVERSION_OUTPUT_DIRNAME,
        "local_only": True,
        "raw_content_included": False,
        "image_bytes_included": False,
        "local_input_paths_included": False,
        "summary_counts": _summary_counts(
            manifest=manifest,
            conversion_report=conversion_report,
            sidecars=sidecars,
            contract=contract,
            command_set_eval=command_set_eval,
            visual_eval=visual_eval,
        ),
        "sidecars": sidecars,
        "contract_validation": contract,
        "command_set_eval": command_set_eval,
        "visual_eval": visual_eval,
    }
    report = LatestNvmeSpecBenchmarkReport.model_validate(report_payload).model_dump(mode="json")
    write_json(config.output_dir / REPORT_FILENAME, report)
    write_text(config.output_dir / SCORECARD_FILENAME, render_scorecard(report))
    return report


def run_latest_nvme_base_benchmark(config: LatestNvmeSpecBenchmarkConfig) -> dict[str, Any]:
    """Compatibility wrapper for the original latest-NVMe-Base benchmark entry point."""
    if config.spec_document_type != BASE_SPEC_DOCUMENT:
        return run_latest_nvme_spec_benchmark(config)
    return run_latest_nvme_spec_benchmark(config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a sanitized latest NVMe Base/NVM Command Set RAG benchmark.")
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--spec-document", choices=SPEC_DOCUMENT_TYPES, default=BASE_SPEC_DOCUMENT)
    parser.add_argument("--mode", choices=BENCHMARK_MODES, default=FULL_PRECISION_MODE)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--pages", default=None)
    parser.add_argument("--page-workers", type=int, default=1)
    parser.add_argument("--visual-mode", action="store_true", help="Use technical_spec_rag_visual option bundle.")
    parser.add_argument("--fail-on-contract-error", action="store_true")
    parser.add_argument("--fail-on-command-eval-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_latest_nvme_spec_benchmark(
        LatestNvmeSpecBenchmarkConfig(
            input_pdf=args.input_pdf,
            output_dir=args.output_dir,
            spec_document_type=args.spec_document,
            mode=args.mode,
            source_url=args.source_url,
            pages=args.pages,
            page_workers=args.page_workers,
            visual_mode=args.visual_mode,
        )
    )
    print(f"Wrote {args.output_dir / REPORT_FILENAME}")
    print(f"Wrote {args.output_dir / SCORECARD_FILENAME}")
    if args.fail_on_contract_error and not report.get("summary_counts", {}).get("contract_validation_passed"):
        return 1
    if args.fail_on_command_eval_error and not report.get("summary_counts", {}).get("command_set_eval_passed", True):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
