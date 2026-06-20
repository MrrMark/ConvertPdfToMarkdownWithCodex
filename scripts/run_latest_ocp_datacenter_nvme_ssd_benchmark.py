#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.config import Config
from pdf2md.models import (
    DomainAdapterMode,
    ImageMode,
    LatestOcpDatacenterNvmeSsdBenchmarkReport,
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
REPORT_FILENAME = "latest_ocp_datacenter_nvme_ssd_benchmark_report.json"
SCORECARD_FILENAME = "latest_ocp_datacenter_nvme_ssd_benchmark_scorecard.md"
CONVERSION_OUTPUT_DIRNAME = "conversion"

FULL_PRECISION_MODE = "full_precision"
FAST_SMOKE_MODE = "fast_smoke"
BENCHMARK_MODES = (FULL_PRECISION_MODE, FAST_SMOKE_MODE)
DEFAULT_FAST_SMOKE_PAGES = "1-5"

OFFICIAL_SOURCE_URL = "https://www.opencompute.org/documents/datacenter-nvme-ssd-specification-v2-7-final-pdf-1"
EXPECTED_SPEC_TITLE = "Datacenter NVMe SSD Specification"
EXPECTED_VERSION = "2.7"
EXPECTED_DATE_MARKER = "01082026"
OCP_EVAL_PROFILE = "ocp_datacenter_nvme_ssd_p2_retrieval"
OCP_EVAL_TOP_K = 8
VISUAL_EVAL_PROFILE = "technical_spec_visual_p3_retrieval"
VISUAL_EVAL_TOP_K = 5
OCP_EVAL_REQUIRED_BUCKETS = (
    "requirement",
    "log_page_requirement",
    "feature_requirement",
    "telemetry_requirement",
    "security_requirement",
    "form_factor_or_thermal_requirement",
)

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
    "page_layout_rag.jsonl",
    "retrieval_chunks_rag.jsonl",
    "tables_rag.jsonl",
    "rag_tables.md",
)


@dataclass(frozen=True)
class LatestOcpDatacenterNvmeSsdBenchmarkConfig:
    input_pdf: Path
    output_dir: Path
    mode: str = FULL_PRECISION_MODE
    source_url: str | None = None
    pages: str | None = None
    page_workers: int = 1
    visual_mode: bool = False


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


def build_option_matrix(*, mode: str, pages: str | None, page_workers: int, visual_mode: bool = False) -> dict[str, Any]:
    """Return the sanitized option matrix used by the OCP benchmark conversion."""
    rag_profile = "technical_spec_rag_visual" if visual_mode else "technical_spec_rag"
    options = rag_profile_options(rag_profile)
    return {
        "benchmark_mode": mode,
        "pages": _effective_pages(mode, pages),
        "page_workers": page_workers,
        "visual_mode": visual_mode,
        "rag_profile": rag_profile,
        "domain_adapter": DomainAdapterMode.OCP.value,
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
        "contract_validator": {
            "ssd_agent_domain": "HIL",
            "ssd_agent_spec_type": DOMAIN_ADAPTER_TO_SPEC_TYPE[DomainAdapterMode.OCP.value],
            "domain_adapter": DomainAdapterMode.OCP.value,
            "require_tables": True,
            "require_domain_units": True,
        },
        "ocp_query_eval": {
            "enabled": True,
            "profile": OCP_EVAL_PROFILE,
            "top_k": OCP_EVAL_TOP_K,
            "required_buckets": list(OCP_EVAL_REQUIRED_BUCKETS),
            "report_policy": "sanitized_metrics_only",
        },
    }


def build_conversion_config(
    *,
    config: LatestOcpDatacenterNvmeSsdBenchmarkConfig,
    conversion_output_dir: Path,
) -> Config:
    """Build the deterministic technical-spec RAG conversion config for the OCP benchmark mode."""
    matrix = build_option_matrix(
        mode=config.mode,
        pages=config.pages,
        page_workers=config.page_workers,
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


def _contract_summary(output_dir: Path, *, source_sha256: str) -> dict[str, Any]:
    try:
        report = validate_ssd_rag_contract(
            output_dir=output_dir,
            ssd_agent_domain="HIL",
            ssd_agent_spec_type=DOMAIN_ADAPTER_TO_SPEC_TYPE[DomainAdapterMode.OCP.value],
            domain_adapter=DomainAdapterMode.OCP.value,
            source_sha256=source_sha256,
            require_tables=True,
            require_domain_units=True,
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


def _text_value(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalized_fields(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("normalized_fields")
    return fields if isinstance(fields, dict) else {}


def _bucket_for_record(record: dict[str, Any]) -> str | None:
    fields = _normalized_fields(record)
    family = str(fields.get("requirement_family") or "")
    if fields.get("related_log_identifier") or family == "log_page":
        return "log_page_requirement"
    if fields.get("related_feature_identifier") or family == "feature":
        return "feature_requirement"
    if fields.get("related_statistic_identifier") or family == "telemetry":
        return "telemetry_requirement"
    if fields.get("related_security_protocol") or family == "security":
        return "security_requirement"
    if fields.get("related_form_factor") or family in {"form_factor", "thermal"}:
        return "form_factor_or_thermal_requirement"
    return None


def _record_query_terms(record: dict[str, Any], *, bucket: str) -> str:
    fields = _normalized_fields(record)
    requirement_id = _text_value(fields, "requirement_id")
    requirement_key = None
    if requirement_id:
        requirement_key = re.sub(r"[^A-Za-z0-9]+", "_", requirement_id).strip("_")
    terms = [
        bucket,
        requirement_id,
        requirement_key,
        _text_value(fields, "requirement_prefix"),
        _text_value(fields, "requirement_family"),
        _text_value(fields, "ocp_section_context"),
        _text_value(fields, "related_command"),
        _text_value(fields, "related_log_identifier"),
        _text_value(fields, "related_feature_identifier"),
        _text_value(fields, "related_statistic_identifier"),
        _text_value(fields, "related_security_protocol"),
        _text_value(fields, "related_form_factor"),
    ]
    return " ".join(term for term in terms if term)


def _ocp_eval_queries(domain_units: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    by_bucket: dict[str, dict[str, Any]] = {}
    first_requirement: dict[str, Any] | None = None
    for record in domain_units:
        if record.get("domain") != DomainAdapterMode.OCP.value or record.get("unit_type") != "requirement":
            continue
        first_requirement = first_requirement or record
        bucket = _bucket_for_record(record)
        if bucket and bucket not in by_bucket:
            by_bucket[bucket] = record
    if first_requirement is not None:
        by_bucket.setdefault("requirement", first_requirement)

    queries: list[dict[str, Any]] = []
    covered_buckets: list[str] = []
    for bucket in OCP_EVAL_REQUIRED_BUCKETS:
        record = by_bucket.get(bucket)
        source_id = _text_value(record or {}, "domain_unit_id")
        if record is None or source_id is None:
            continue
        queries.append(
            {
                "query": _record_query_terms(record, bucket=bucket),
                "expected_source_ids": [source_id],
                "expected_source_types": ["domain_unit"],
                "expected_table_field_source_ids": [source_id],
                "expected_table_field_source_types": ["domain_unit"],
            }
        )
        covered_buckets.append(bucket)
    missing_buckets = [bucket for bucket in OCP_EVAL_REQUIRED_BUCKETS if bucket not in by_bucket]
    return queries, covered_buckets, missing_buckets


def _ocp_eval_summary(output_dir: Path) -> dict[str, Any]:
    try:
        domain_units = _read_jsonl_records(output_dir / "domain_units_rag.jsonl")
        retrieval_chunks = _read_jsonl_records(output_dir / "retrieval_chunks_rag.jsonl")
        queries, covered_buckets, missing_buckets = _ocp_eval_queries(domain_units)
        if not retrieval_chunks or not queries:
            return {
                "status": "failed",
                "passed": False,
                "profile": OCP_EVAL_PROFILE,
                "top_k": OCP_EVAL_TOP_K,
                "query_count": len(queries),
                "required_buckets": list(OCP_EVAL_REQUIRED_BUCKETS),
                "covered_buckets": covered_buckets,
                "missing_buckets": missing_buckets,
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
        eval_report = evaluate_queries(chunks=retrieval_chunks, queries=queries, top_k=OCP_EVAL_TOP_K)
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        return {
            "status": "failed",
            "passed": False,
            "profile": OCP_EVAL_PROFILE,
            "top_k": OCP_EVAL_TOP_K,
            "query_count": 0,
            "required_buckets": list(OCP_EVAL_REQUIRED_BUCKETS),
            "covered_buckets": [],
            "missing_buckets": list(OCP_EVAL_REQUIRED_BUCKETS),
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
        not missing_buckets
        and sanitized_metrics["hit_at_k"] >= 1.0
        and sanitized_metrics["expected_source_coverage"] >= 1.0
        and sanitized_metrics["table_field_coverage"] >= 1.0
    )
    return {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "profile": OCP_EVAL_PROFILE,
        "top_k": OCP_EVAL_TOP_K,
        "query_count": len(queries),
        "required_buckets": list(OCP_EVAL_REQUIRED_BUCKETS),
        "covered_buckets": covered_buckets,
        "missing_buckets": missing_buckets,
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
    ocp_eval: dict[str, Any],
    visual_eval: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    conversion_summary = _summary(conversion_report)
    contract_summary = _summary(contract)
    page_count = _int_value(conversion_summary, "processed_pages")
    if page_count == 0 and isinstance(manifest.get("selected_pages"), list):
        page_count = len(manifest["selected_pages"])
    conversion_error_count = 1 if str(conversion_report.get("status") or "") == "failed" else 0
    contract_error_count = _int_value(contract_summary, "error_count")
    ocp_eval_metrics = ocp_eval.get("metrics")
    ocp_eval_metrics = ocp_eval_metrics if isinstance(ocp_eval_metrics, dict) else {}
    visual_eval_metrics = visual_eval.get("metrics")
    visual_eval_metrics = visual_eval_metrics if isinstance(visual_eval_metrics, dict) else {}
    conversion_warning_count = _int_value(conversion_summary, "warning_count")
    contract_warning_count = _int_value(contract_summary, "warning_count")
    domain_units = _read_jsonl_records(output_dir / "domain_units_rag.jsonl")
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
        "ocp_requirement_unit_count": sum(
            1
            for record in domain_units
            if record.get("domain") == DomainAdapterMode.OCP.value and record.get("unit_type") == "requirement"
        ),
        "page_layout_record_count": _int_value(conversion_summary, "page_layout_record_count"),
        "layout_region_ref_count": _int_value(conversion_summary, "layout_region_ref_count"),
        "layout_caption_link_count": _int_value(conversion_summary, "layout_caption_link_count"),
        "layout_multi_column_page_count": _int_value(conversion_summary, "layout_multi_column_page_count"),
        "layout_header_footer_suppressed_page_count": _int_value(
            conversion_summary,
            "layout_header_footer_suppressed_page_count",
        ),
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
        "ocp_eval_status": ocp_eval.get("status"),
        "ocp_eval_passed": ocp_eval.get("passed") is True,
        "ocp_eval_query_count": _int_value(ocp_eval, "query_count"),
        "ocp_eval_expected_source_coverage": _float_value(ocp_eval_metrics, "expected_source_coverage"),
        "ocp_eval_hit_at_k": _float_value(ocp_eval_metrics, "hit_at_k"),
        "ocp_eval_table_field_coverage": _float_value(ocp_eval_metrics, "table_field_coverage"),
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
        "# Latest OCP Datacenter NVMe SSD Benchmark Scorecard",
        "",
        f"- Expected spec: `{report.get('expected_spec_title')}`",
        f"- Expected version: `{report.get('expected_version')}`",
        f"- Expected date marker: `{report.get('expected_date_marker')}`",
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
        f"| ocp_requirement_unit_count | {counts.get('ocp_requirement_unit_count', 0)} |",
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
        f"| ocp_eval_status | {counts.get('ocp_eval_status')} |",
        f"| ocp_eval_passed | {counts.get('ocp_eval_passed')} |",
        f"| ocp_eval_query_count | {counts.get('ocp_eval_query_count', 0)} |",
        f"| ocp_eval_expected_source_coverage | {counts.get('ocp_eval_expected_source_coverage', 0.0)} |",
        f"| ocp_eval_hit_at_k | {counts.get('ocp_eval_hit_at_k', 0.0)} |",
        f"| ocp_eval_table_field_coverage | {counts.get('ocp_eval_table_field_coverage', 0.0)} |",
        f"| warning_count | {counts.get('warning_count', 0)} |",
        f"| error_count | {counts.get('error_count', 0)} |",
    ]
    return "\n".join(lines) + "\n"


def run_latest_ocp_datacenter_nvme_ssd_benchmark(
    config: LatestOcpDatacenterNvmeSsdBenchmarkConfig,
) -> dict[str, Any]:
    """Run a latest-OCP Datacenter NVMe SSD technical RAG benchmark and write sanitized reports."""
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
    ocp_eval = _ocp_eval_summary(conversion_output_dir)
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
    report_payload = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "latest_ocp_datacenter_nvme_ssd_benchmark",
        "expected_spec_title": EXPECTED_SPEC_TITLE,
        "expected_version": EXPECTED_VERSION,
        "expected_date_marker": EXPECTED_DATE_MARKER,
        "source_url": config.source_url or OFFICIAL_SOURCE_URL,
        "source_sha256": source_sha256,
        "mode": config.mode,
        "option_matrix": build_option_matrix(
            mode=config.mode,
            pages=config.pages,
            page_workers=config.page_workers,
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
            ocp_eval=ocp_eval,
            visual_eval=visual_eval,
            output_dir=conversion_output_dir,
        ),
        "sidecars": sidecars,
        "contract_validation": contract,
        "ocp_eval": ocp_eval,
        "visual_eval": visual_eval,
    }
    report = LatestOcpDatacenterNvmeSsdBenchmarkReport.model_validate(report_payload).model_dump(mode="json")
    write_json(config.output_dir / REPORT_FILENAME, report)
    write_text(config.output_dir / SCORECARD_FILENAME, render_scorecard(report))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a sanitized latest OCP Datacenter NVMe SSD RAG benchmark.")
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=BENCHMARK_MODES, default=FULL_PRECISION_MODE)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--pages", default=None)
    parser.add_argument("--page-workers", type=int, default=1)
    parser.add_argument("--visual-mode", action="store_true", help="Use technical_spec_rag_visual option bundle.")
    parser.add_argument("--fail-on-contract-error", action="store_true")
    parser.add_argument("--fail-on-ocp-eval-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_latest_ocp_datacenter_nvme_ssd_benchmark(
        LatestOcpDatacenterNvmeSsdBenchmarkConfig(
            input_pdf=args.input_pdf,
            output_dir=args.output_dir,
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
    if args.fail_on_ocp_eval_error and not report.get("summary_counts", {}).get("ocp_eval_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
