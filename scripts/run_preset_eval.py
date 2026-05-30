#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.config import Config
from pdf2md.models import DomainAdapterMode
from pdf2md.pipeline import run_conversion
from pdf2md.rag_profiles import SUPPORTED_RAG_PURPOSE_PROFILES, rag_profile_options
from pdf2md.utils.io import write_json, write_text

try:
    from scripts import run_rag_eval
    from scripts.validate_artifact_integrity import validate_artifact_integrity
    from scripts.validate_index_contract import validate_index_contract
    from scripts.validate_provenance_integrity import validate_provenance_integrity
    from scripts.validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import run_rag_eval  # type: ignore[no-redef]
    from validate_artifact_integrity import validate_artifact_integrity  # type: ignore[no-redef]
    from validate_index_contract import validate_index_contract  # type: ignore[no-redef]
    from validate_provenance_integrity import validate_provenance_integrity  # type: ignore[no-redef]
    from validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract  # type: ignore[no-redef]


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "preset_eval_report.json"
COMPARISON_FILENAME = "preset_artifact_comparison.json"
SCORECARD_FILENAME = "preset_scorecard.md"
DEFAULT_PRESETS = ("rag_optimized", "technical_spec_rag")
NONE_DOMAIN_ADAPTER = DomainAdapterMode.NONE.value
ARTIFACT_FILES = (
    "document.md",
    "manifest.json",
    "report.json",
    "text_blocks_rag.jsonl",
    "semantic_units_rag.jsonl",
    "requirements_rag.jsonl",
    "cross_refs_rag.jsonl",
    "requirement_traceability_rag.jsonl",
    "technical_tables_rag.jsonl",
    "figures_rag.jsonl",
    "domain_units_rag.jsonl",
    "retrieval_chunks_rag.jsonl",
    "tables_rag.jsonl",
    "rag_tables.md",
)


@dataclass(frozen=True)
class PresetEvalConfig:
    input_pdf: Path
    output_root: Path
    presets: tuple[str, ...] = DEFAULT_PRESETS
    domain_adapter: str = NONE_DOMAIN_ADAPTER
    pages: str | None = None
    rag_eval_set: Path | None = None
    rag_top_k: int = 5
    rag_thresholds: dict[str, float] | None = None
    min_score: float | None = None
    fail_on_threshold: bool = False


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clamp_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))


def _int_value(mapping: dict[str, Any], key: str, default: int = 0) -> int:
    value = mapping.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _float_value(mapping: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = mapping.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    return summary if isinstance(summary, dict) else {}


def _status(report: dict[str, Any]) -> str:
    return str(report.get("status") or "")


def _validator_counts(report: dict[str, Any]) -> tuple[int, int]:
    summary = _summary(report)
    return _int_value(summary, "error_count"), _int_value(summary, "warning_count")


def _validator_health_ratio(reports: list[dict[str, Any]]) -> float:
    if not reports:
        return 0.0
    error_count = 0
    warning_count = 0
    for report in reports:
        errors, warnings = _validator_counts(report)
        error_count += errors
        warning_count += warnings
    if error_count:
        return 0.0
    if warning_count:
        return 0.5
    return 1.0


def _score_component(
    *,
    code: str,
    label: str,
    max_points: float,
    ratio: float,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    normalized = _clamp_ratio(ratio)
    return {
        "code": code,
        "label": label,
        "earned": round(max_points * normalized, 2),
        "max": max_points,
        "ratio": round(normalized, 4),
        "evidence": evidence,
    }


def _sidecar_coverage_ratio(summary: dict[str, Any]) -> float:
    required_file_fields = (
        "rag_text_block_file_count",
        "semantic_unit_file_count",
        "retrieval_chunk_file_count",
    )
    required_ratio = sum(1 for field in required_file_fields if _int_value(summary, field) > 0) / len(
        required_file_fields
    )
    specialist_record_fields = (
        "rag_table_record_count",
        "requirement_record_count",
        "requirement_traceability_record_count",
        "technical_table_record_count",
        "figure_rag_record_count",
    )
    specialist_hits = sum(1 for field in specialist_record_fields if _int_value(summary, field) > 0)
    return (required_ratio * 0.7) + (min(specialist_hits / 3, 1.0) * 0.3)


def _cross_ref_coverage(summary: dict[str, Any], rag_eval_report: dict[str, Any] | None) -> float:
    if rag_eval_report:
        metrics = rag_eval_report.get("metrics")
        if isinstance(metrics, dict) and "cross_ref_resolved_coverage" in metrics:
            value = metrics.get("cross_ref_resolved_coverage")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return _clamp_ratio(float(value))
    total = _int_value(summary, "cross_ref_record_count")
    if total <= 0:
        return 1.0
    unresolved = _int_value(summary, "unresolved_cross_ref_count")
    return _clamp_ratio((total - unresolved) / total)


def _status_ratio(report: dict[str, Any]) -> float:
    status = _status(report)
    if status == "success":
        return 1.0
    if status == "partial_success":
        failed_pages = report.get("failed_pages")
        return 0.7 if not failed_pages else 0.4
    return 0.0


def _rag_components(
    *,
    conversion_report: dict[str, Any],
    validation_reports: list[dict[str, Any]],
    rag_eval_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    summary = _summary(conversion_report)
    actionable_warnings = _int_value(summary, "actionable_warning_count")
    chunk_count = _int_value(summary, "retrieval_chunk_record_count")
    over_target_count = _int_value(summary, "retrieval_chunk_over_target_count")
    duplicate_count = _int_value(summary, "retrieval_chunk_duplicate_source_ref_count")
    metrics = rag_eval_report.get("metrics", {}) if isinstance(rag_eval_report, dict) else {}
    source_ref_presence = _float_value(metrics, "source_ref_presence_coverage", 1.0 if chunk_count else 0.0)
    duplicate_ratio = _float_value(
        metrics,
        "duplicate_source_ratio",
        (duplicate_count / chunk_count) if chunk_count else 1.0,
    )
    return [
        _score_component(
            code="integrity",
            label="artifact/index/provenance integrity",
            max_points=20,
            ratio=_validator_health_ratio(validation_reports),
            evidence=_validation_issue_summary(validation_reports),
        ),
        _score_component(
            code="actionable_warning",
            label="actionable warning",
            max_points=15,
            ratio=1.0 - min(actionable_warnings / 10, 1.0),
            evidence={"actionable_warning_count": actionable_warnings},
        ),
        _score_component(
            code="chunk_token_compliance",
            label="chunk token compliance",
            max_points=15,
            ratio=(1.0 - (over_target_count / chunk_count)) if chunk_count else 0.0,
            evidence={"retrieval_chunk_record_count": chunk_count, "retrieval_chunk_over_target_count": over_target_count},
        ),
        _score_component(
            code="source_refs",
            label="source-ref presence/duplicate guard",
            max_points=15,
            ratio=(source_ref_presence * 0.7) + ((1.0 - duplicate_ratio) * 0.3),
            evidence={
                "source_ref_presence_coverage": source_ref_presence,
                "duplicate_source_ratio": round(duplicate_ratio, 4),
                "duplicate_source_ref_count": duplicate_count,
            },
        ),
        _score_component(
            code="sidecar_coverage",
            label="table/requirement/figure sidecar coverage",
            max_points=15,
            ratio=_sidecar_coverage_ratio(summary),
            evidence={
                "rag_table_record_count": _int_value(summary, "rag_table_record_count"),
                "requirement_record_count": _int_value(summary, "requirement_record_count"),
                "figure_rag_record_count": _int_value(summary, "figure_rag_record_count"),
            },
        ),
        _score_component(
            code="cross_refs",
            label="cross-ref resolved coverage",
            max_points=10,
            ratio=_cross_ref_coverage(summary, rag_eval_report),
            evidence={
                "cross_ref_record_count": _int_value(summary, "cross_ref_record_count"),
                "unresolved_cross_ref_count": _int_value(summary, "unresolved_cross_ref_count"),
            },
        ),
        _score_component(
            code="performance_repeatability",
            label="conversion performance/repeatability",
            max_points=10,
            ratio=_status_ratio(conversion_report),
            evidence={
                "status": _status(conversion_report),
                "pages_per_second": summary.get("pages_per_second"),
                "duration_ms": conversion_report.get("duration_ms"),
            },
        ),
    ]


def _technical_components(
    *,
    conversion_report: dict[str, Any],
    validation_reports: list[dict[str, Any]],
    ssd_report: dict[str, Any] | None,
    rag_eval_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    summary = _summary(conversion_report)
    domain_count = _int_value(summary, "domain_unit_record_count")
    technical_table_count = _int_value(summary, "technical_table_record_count")
    requirement_count = _int_value(summary, "requirement_record_count")
    traceability_count = _int_value(summary, "requirement_traceability_record_count")
    actionable_warnings = _int_value(summary, "actionable_warning_count")
    requirement_ratio = 0.5 if requirement_count == 0 and _int_value(summary, "requirement_traceability_file_count") else 0.0
    if requirement_count:
        requirement_ratio = min(traceability_count / requirement_count, 1.0)
    return [
        _score_component(
            code="domain_unit_coverage",
            label="domain unit coverage",
            max_points=20,
            ratio=1.0 if domain_count > 0 else 0.0,
            evidence={"domain_unit_record_count": domain_count},
        ),
        _score_component(
            code="technical_table_typed_coverage",
            label="technical table typed coverage",
            max_points=15,
            ratio=1.0 if technical_table_count > 0 else 0.0,
            evidence={"technical_table_record_count": technical_table_count},
        ),
        _score_component(
            code="requirement_traceability",
            label="requirement traceability",
            max_points=15,
            ratio=requirement_ratio,
            evidence={
                "requirement_record_count": requirement_count,
                "requirement_traceability_record_count": traceability_count,
            },
        ),
        _score_component(
            code="cross_refs",
            label="cross-ref resolved coverage",
            max_points=15,
            ratio=_cross_ref_coverage(summary, rag_eval_report),
            evidence={
                "cross_ref_record_count": _int_value(summary, "cross_ref_record_count"),
                "unresolved_cross_ref_count": _int_value(summary, "unresolved_cross_ref_count"),
            },
        ),
        _score_component(
            code="ssd_contract",
            label="SSD contract validation",
            max_points=15,
            ratio=1.0 if ssd_report and ssd_report.get("passed") is True else 0.0,
            evidence=_ssd_contract_evidence(ssd_report),
        ),
        _score_component(
            code="integrity",
            label="artifact/index/provenance integrity",
            max_points=10,
            ratio=_validator_health_ratio(validation_reports),
            evidence=_validation_issue_summary(validation_reports),
        ),
        _score_component(
            code="warning_performance",
            label="actionable warning/performance",
            max_points=10,
            ratio=((1.0 - min(actionable_warnings / 10, 1.0)) * 0.5) + (_status_ratio(conversion_report) * 0.5),
            evidence={
                "actionable_warning_count": actionable_warnings,
                "status": _status(conversion_report),
                "pages_per_second": summary.get("pages_per_second"),
            },
        ),
    ]


def _validation_issue_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    error_count = 0
    warning_count = 0
    for report in reports:
        errors, warnings = _validator_counts(report)
        error_count += errors
        warning_count += warnings
    return {"validation_error_count": error_count, "validation_warning_count": warning_count}


def _ssd_contract_evidence(ssd_report: dict[str, Any] | None) -> dict[str, Any]:
    if not ssd_report:
        return {"status": "not_run", "passed": False}
    summary = _summary(ssd_report)
    return {
        "status": "passed" if ssd_report.get("passed") is True else "failed",
        "passed": ssd_report.get("passed") is True,
        "error_count": _int_value(summary, "error_count"),
        "warning_count": _int_value(summary, "warning_count"),
        "domain_unit_count": _int_value(summary, "domain_unit_count"),
        "technical_table_row_count": _int_value(summary, "technical_table_row_count"),
    }


def _condition(
    *,
    code: str,
    passed: bool,
    actual: Any,
    expected: Any,
    severity: str = "required",
) -> dict[str, Any]:
    return {
        "code": code,
        "passed": passed,
        "actual": actual,
        "expected": expected,
        "severity": severity,
    }


def _build_gate(
    *,
    preset: str,
    domain_adapter: str | None,
    conversion_report: dict[str, Any],
    validation_reports: list[dict[str, Any]],
    ssd_report: dict[str, Any] | None,
    rag_eval_report: dict[str, Any] | None,
    score: float,
    min_score: float | None,
) -> dict[str, Any]:
    summary = _summary(conversion_report)
    validation_issue_summary = _validation_issue_summary(validation_reports)
    conditions: list[dict[str, Any]] = []
    if preset == "technical_spec_rag":
        effective_domain = (domain_adapter or NONE_DOMAIN_ADAPTER).strip().lower()
        domain_present = bool(effective_domain and effective_domain != NONE_DOMAIN_ADAPTER)
        conditions.extend(
            [
                _condition(
                    code="technical_domain_adapter_present",
                    passed=domain_present,
                    actual=effective_domain or NONE_DOMAIN_ADAPTER,
                    expected="non-none",
                ),
                _condition(
                    code="domain_units_present",
                    passed=_int_value(summary, "domain_unit_record_count") > 0,
                    actual=_int_value(summary, "domain_unit_record_count"),
                    expected="> 0",
                ),
                _condition(
                    code="technical_tables_present",
                    passed=_int_value(summary, "technical_table_record_count") > 0,
                    actual=_int_value(summary, "technical_table_record_count"),
                    expected="> 0",
                ),
                _condition(
                    code="ssd_contract_passed",
                    passed=bool(ssd_report and ssd_report.get("passed") is True),
                    actual=bool(ssd_report and ssd_report.get("passed") is True),
                    expected=True,
                ),
            ]
        )
        if rag_eval_report and "passed_calibration_gate" in rag_eval_report:
            conditions.append(
                _condition(
                    code="rag_eval_thresholds_passed",
                    passed=rag_eval_report.get("passed_calibration_gate") is True,
                    actual=rag_eval_report.get("passed_calibration_gate"),
                    expected=True,
                )
            )
    else:
        conditions.extend(
            [
                _condition(
                    code="actionable_warnings_zero",
                    passed=_int_value(summary, "actionable_warning_count") == 0,
                    actual=_int_value(summary, "actionable_warning_count"),
                    expected=0,
                ),
                _condition(
                    code="chunk_over_target_zero",
                    passed=_int_value(summary, "retrieval_chunk_over_target_count") == 0,
                    actual=_int_value(summary, "retrieval_chunk_over_target_count"),
                    expected=0,
                ),
                _condition(
                    code="integrity_warnings_zero",
                    passed=validation_issue_summary["validation_error_count"] == 0
                    and validation_issue_summary["validation_warning_count"] == 0,
                    actual=validation_issue_summary,
                    expected={"validation_error_count": 0, "validation_warning_count": 0},
                ),
            ]
        )
    if min_score is not None:
        conditions.append(
            _condition(
                code="min_score",
                passed=score >= min_score,
                actual=score,
                expected=f">= {min_score}",
            )
        )
    required_conditions = [condition for condition in conditions if condition["severity"] == "required"]
    return {
        "passed": all(condition["passed"] for condition in required_conditions),
        "conditions": conditions,
        "failed_conditions": [condition for condition in required_conditions if not condition["passed"]],
    }


def _score_metrics(
    *,
    conversion_report: dict[str, Any],
    validation_reports: list[dict[str, Any]],
    ssd_report: dict[str, Any] | None,
    rag_eval_report: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = _summary(conversion_report)
    validation_issue_summary = _validation_issue_summary(validation_reports)
    metrics = {
        "actionable_warning_count": _int_value(summary, "actionable_warning_count"),
        "warning_count": _int_value(summary, "warning_count"),
        "retrieval_chunk_record_count": _int_value(summary, "retrieval_chunk_record_count"),
        "retrieval_chunk_over_target_count": _int_value(summary, "retrieval_chunk_over_target_count"),
        "retrieval_chunk_duplicate_source_ref_count": _int_value(
            summary,
            "retrieval_chunk_duplicate_source_ref_count",
        ),
        "domain_unit_record_count": _int_value(summary, "domain_unit_record_count"),
        "technical_table_record_count": _int_value(summary, "technical_table_record_count"),
        "requirement_record_count": _int_value(summary, "requirement_record_count"),
        "requirement_traceability_record_count": _int_value(summary, "requirement_traceability_record_count"),
        "rag_table_record_count": _int_value(summary, "rag_table_record_count"),
        "figure_rag_record_count": _int_value(summary, "figure_rag_record_count"),
        "cross_ref_record_count": _int_value(summary, "cross_ref_record_count"),
        "unresolved_cross_ref_count": _int_value(summary, "unresolved_cross_ref_count"),
        "pages_per_second": summary.get("pages_per_second"),
        "duration_ms": conversion_report.get("duration_ms"),
        **validation_issue_summary,
        "ssd_contract_passed": bool(ssd_report and ssd_report.get("passed") is True),
    }
    if rag_eval_report:
        rag_metrics = rag_eval_report.get("metrics")
        if isinstance(rag_metrics, dict):
            for key in (
                "hit_at_k",
                "mrr",
                "expected_source_coverage",
                "requirement_coverage",
                "table_field_coverage",
                "cross_ref_resolved_coverage",
                "chunk_size_compliance",
                "source_ref_presence_coverage",
                "relationship_target_coverage",
                "chunk_token_p95",
                "chunk_token_max",
                "duplicate_source_ratio",
            ):
                if key in rag_metrics:
                    metrics[f"rag_eval_{key}"] = rag_metrics[key]
        if "passed_calibration_gate" in rag_eval_report:
            metrics["rag_eval_passed_calibration_gate"] = rag_eval_report["passed_calibration_gate"]
    return metrics


def score_preset_result(
    *,
    preset: str,
    domain_adapter: str | None = None,
    conversion_report: dict[str, Any] | None = None,
    artifact_report: dict[str, Any] | None = None,
    index_report: dict[str, Any] | None = None,
    provenance_report: dict[str, Any] | None = None,
    ssd_report: dict[str, Any] | None = None,
    rag_eval_report: dict[str, Any] | None = None,
    min_score: float | None = None,
) -> dict[str, Any]:
    """Score one preset output with purpose-specific local quality criteria."""
    conversion_report = conversion_report or {}
    validation_reports = [report for report in (artifact_report, index_report, provenance_report) if report]
    if preset == "technical_spec_rag":
        components = _technical_components(
            conversion_report=conversion_report,
            validation_reports=validation_reports,
            ssd_report=ssd_report,
            rag_eval_report=rag_eval_report,
        )
    else:
        components = _rag_components(
            conversion_report=conversion_report,
            validation_reports=validation_reports,
            rag_eval_report=rag_eval_report,
        )
    score = round(sum(float(component["earned"]) for component in components), 2)
    gate = _build_gate(
        preset=preset,
        domain_adapter=domain_adapter,
        conversion_report=conversion_report,
        validation_reports=validation_reports,
        ssd_report=ssd_report,
        rag_eval_report=rag_eval_report,
        score=score,
        min_score=min_score,
    )
    return {
        "preset": preset,
        "domain_adapter": domain_adapter or NONE_DOMAIN_ADAPTER,
        "score": score,
        "max_score": 100,
        "components": components,
        "metrics": _score_metrics(
            conversion_report=conversion_report,
            validation_reports=validation_reports,
            ssd_report=ssd_report,
            rag_eval_report=rag_eval_report,
        ),
        "gate": gate,
    }


def _effective_domain_adapter(preset: str, domain_adapter: str) -> str:
    if preset == "technical_spec_rag":
        return domain_adapter
    return NONE_DOMAIN_ADAPTER


def _output_label(preset: str, domain_adapter: str) -> str:
    effective_domain = _effective_domain_adapter(preset, domain_adapter)
    if preset == "technical_spec_rag" and effective_domain != NONE_DOMAIN_ADAPTER:
        return f"{preset}__{effective_domain}"
    return preset


def build_config_for_preset(
    *,
    input_pdf: Path,
    output_dir: Path,
    preset: str,
    domain_adapter: str,
    pages: str | None = None,
) -> Config:
    """Build the same option matrix used by GUI preset selection."""
    options = rag_profile_options(preset)
    effective_domain = _effective_domain_adapter(preset, domain_adapter)
    return Config(
        input_pdf=input_pdf,
        output_dir=output_dir,
        pages=pages,
        image_mode=options.image_mode,
        table_mode=options.table_mode,
        rag_table_output=options.rag_table_output,
        rag_profile=preset,
        domain_adapter=effective_domain,
        confidential_safe_mode=options.confidential_safe_mode,
        force_ocr=options.force_ocr,
        keep_page_markers=options.keep_page_markers,
        remove_header_footer=options.remove_header_footer,
        dedupe_images=options.dedupe_images,
        repair_hyphenation=options.repair_hyphenation,
        figure_crop_fallback=options.figure_crop_fallback,
        retrieval_chunk_max_tokens=options.retrieval_chunk_max_tokens,
        retrieval_tokenizer=options.retrieval_tokenizer,
        rag_contextual_embedding_text=options.rag_contextual_embedding_text,
        rag_merge_sibling_text_chunks=options.rag_merge_sibling_text_chunks,
        rag_chunk_relationship_metadata=options.rag_chunk_relationship_metadata,
    )


def _validator_summary(name: str, report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"name": name, "status": "not_run", "passed": False, "summary": {}}
    summary = _summary(report)
    return {
        "name": name,
        "status": str(report.get("status") or ("passed" if report.get("passed") else "failed")),
        "passed": bool(report.get("passed")),
        "summary": {
            key: summary[key]
            for key in sorted(summary)
            if key.endswith("_count")
            or key in {
                "checked_files",
                "checked_records",
                "checked_links",
                "checked_assets",
                "checked_source_refs",
                "resolved_source_refs",
                "unresolved_source_refs",
            }
        },
        "finding_codes": _finding_codes(report),
    }


def _finding_codes(report: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field in ("findings", "errors", "warnings"):
        records = report.get(field)
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            code = str(record.get("code") or "unknown")
            counts[code] = counts.get(code, 0) + 1
    return counts


def _error_report(*, purpose: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": purpose,
        "status": "failed",
        "passed": False,
        "summary": {"error_count": 1, "warning_count": 0},
        "findings": [{"severity": "error", "code": code, "message": message}],
    }


def run_output_validators(*, output_dir: Path, preset: str, domain_adapter: str) -> dict[str, dict[str, Any] | None]:
    try:
        artifact_report = validate_artifact_integrity(output_dir=output_dir)
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        artifact_report = _error_report(
            purpose="output_artifact_integrity_validation",
            code="artifact_integrity_exception",
            message=type(exc).__name__,
        )
    try:
        index_report = validate_index_contract(output_dir=output_dir)
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        index_report = _error_report(
            purpose="rag_index_contract_validation",
            code="index_contract_exception",
            message=type(exc).__name__,
        )
    try:
        provenance_report = validate_provenance_integrity(output_dir=output_dir)
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        provenance_report = _error_report(
            purpose="rag_provenance_integrity_validation",
            code="provenance_integrity_exception",
            message=type(exc).__name__,
        )
    ssd_report = None
    if preset == "technical_spec_rag" and domain_adapter != NONE_DOMAIN_ADAPTER:
        try:
            ssd_report = validate_ssd_rag_contract(
                output_dir=output_dir,
                ssd_agent_domain="HIL",
                ssd_agent_spec_type=DOMAIN_ADAPTER_TO_SPEC_TYPE[domain_adapter],
                domain_adapter=domain_adapter,
                require_tables=True,
                require_domain_units=True,
            )
        except Exception as exc:  # pragma: no cover - defensive runner boundary
            ssd_report = _error_report(
                purpose="ssd_rag_contract_validation",
                code="ssd_contract_exception",
                message=type(exc).__name__,
            )
    return {
        "artifact_integrity": artifact_report,
        "index_contract": index_report,
        "provenance_integrity": provenance_report,
        "ssd_contract": ssd_report,
    }


def _rag_thresholds(config: PresetEvalConfig) -> dict[str, float]:
    return dict(config.rag_thresholds or {})


def run_optional_rag_eval(*, output_dir: Path, config: PresetEvalConfig) -> dict[str, Any] | None:
    if config.rag_eval_set is None:
        return None
    try:
        chunks = run_rag_eval._read_jsonl(output_dir / "retrieval_chunks_rag.jsonl")
        queries = run_rag_eval._load_eval_set(config.rag_eval_set)
        report = run_rag_eval.evaluate_queries(
            chunks=chunks,
            queries=queries,
            top_k=config.rag_top_k,
        )
        report["metrics"].update(run_rag_eval.collect_output_diagnostics(output_dir))
    except Exception as exc:  # pragma: no cover - defensive runner boundary
        return {
            "schema_version": SCHEMA_VERSION,
            "top_k": config.rag_top_k,
            "query_count": 0,
            "metrics": {},
            "gate_failures": [
                {
                    "type": "rag_eval_exception",
                    "metric": "rag_eval",
                    "current": type(exc).__name__,
                    "direction": "available",
                }
            ],
            "passed_calibration_gate": False,
        }
    thresholds = _rag_thresholds(config)
    if thresholds or config.fail_on_threshold:
        report = run_rag_eval.apply_calibration_gate(
            report,
            calibration_profile="preset-eval",
            thresholds=thresholds,
        )
    return report


def collect_artifact_summary(output_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for file_name in ARTIFACT_FILES:
        path = output_dir / file_name
        files.append(
            {
                "file": file_name,
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
                "record_count": _read_jsonl_count(path) if file_name.endswith(".jsonl") else 0,
            }
        )
    image_dir = output_dir / "assets" / "images"
    image_files = sorted(path for path in image_dir.glob("*") if path.is_file()) if image_dir.exists() else []
    return {
        "files": files,
        "image_asset_count": len(image_files),
        "image_asset_bytes": sum(path.stat().st_size for path in image_files),
    }


def _conversion_summary(report: dict[str, Any], *, exit_code: int, output_label: str) -> dict[str, Any]:
    summary = _summary(report)
    warnings = report.get("warnings")
    warning_codes: dict[str, int] = {}
    if isinstance(warnings, list):
        for warning in warnings:
            if isinstance(warning, dict):
                code = str(warning.get("code") or "unknown")
                warning_codes[code] = warning_codes.get(code, 0) + 1
    return {
        "output_label": output_label,
        "status": _status(report),
        "exit_code": exit_code,
        "duration_ms": report.get("duration_ms"),
        "processed_pages": _int_value(summary, "processed_pages"),
        "warning_count": _int_value(summary, "warning_count"),
        "actionable_warning_count": _int_value(summary, "actionable_warning_count"),
        "advisory_warning_count": _int_value(summary, "advisory_warning_count"),
        "failed_page_count": _int_value(summary, "failed_page_count"),
        "pages_per_second": summary.get("pages_per_second"),
        "warning_codes": warning_codes,
    }


def _sanitized_rag_eval_summary(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None
    metrics = report.get("metrics")
    return {
        "top_k": report.get("top_k"),
        "query_count": report.get("query_count"),
        "metrics": metrics if isinstance(metrics, dict) else {},
        "passed_calibration_gate": report.get("passed_calibration_gate"),
        "gate_failure_count": len(report.get("gate_failures") or []),
    }


def evaluate_one_preset(*, config: PresetEvalConfig, preset: str, source_sha256: str) -> dict[str, Any]:
    domain_adapter = _effective_domain_adapter(preset, config.domain_adapter)
    output_label = _output_label(preset, config.domain_adapter)
    output_dir = config.output_root / output_label
    conversion_config = build_config_for_preset(
        input_pdf=config.input_pdf,
        output_dir=output_dir,
        preset=preset,
        domain_adapter=config.domain_adapter,
        pages=config.pages,
    )
    try:
        result = run_conversion(conversion_config)
        exit_code = result.exit_code
        conversion_report = _as_dict(result.report) or _read_json(output_dir / "report.json")
    except Exception:  # pragma: no cover - defensive runner boundary
        output_dir.mkdir(parents=True, exist_ok=True)
        exit_code = 1
        conversion_report = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed",
            "duration_ms": None,
            "warnings": [{"code": "PRESET_CONVERSION_FAILED"}],
            "summary": {
                "processed_pages": 0,
                "warning_count": 1,
                "actionable_warning_count": 1,
                "advisory_warning_count": 0,
                "failed_page_count": 0,
            },
        }
    validator_reports = run_output_validators(output_dir=output_dir, preset=preset, domain_adapter=domain_adapter)
    rag_eval_report = run_optional_rag_eval(output_dir=output_dir, config=config)
    score = score_preset_result(
        preset=preset,
        domain_adapter=domain_adapter,
        conversion_report=conversion_report,
        artifact_report=validator_reports["artifact_integrity"],
        index_report=validator_reports["index_contract"],
        provenance_report=validator_reports["provenance_integrity"],
        ssd_report=validator_reports["ssd_contract"],
        rag_eval_report=rag_eval_report,
        min_score=config.min_score,
    )
    return {
        "preset": preset,
        "domain_adapter": domain_adapter,
        "output_label": output_label,
        "output_dir": output_label,
        "input_pdf_name": config.input_pdf.name,
        "source_sha256": source_sha256,
        "conversion": _conversion_summary(conversion_report, exit_code=exit_code, output_label=output_label),
        "artifacts": collect_artifact_summary(output_dir),
        "validators": {
            "artifact_integrity": _validator_summary("artifact_integrity", validator_reports["artifact_integrity"]),
            "index_contract": _validator_summary("index_contract", validator_reports["index_contract"]),
            "provenance_integrity": _validator_summary("provenance_integrity", validator_reports["provenance_integrity"]),
            "ssd_contract": _validator_summary("ssd_contract", validator_reports["ssd_contract"]),
        },
        "rag_eval": _sanitized_rag_eval_summary(rag_eval_report),
        "score": score,
    }


def build_preset_artifact_comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a sanitized preset comparison without copying artifact contents."""
    presets: list[dict[str, Any]] = []
    for result in results:
        score = result.get("score") if isinstance(result.get("score"), dict) else {}
        metrics = score.get("metrics") if isinstance(score, dict) else {}
        artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
        files = artifacts.get("files") if isinstance(artifacts, dict) else []
        file_summary = {
            str(file_record.get("file")): {
                "exists": bool(file_record.get("exists")),
                "bytes": int(file_record.get("bytes") or 0),
                "record_count": int(file_record.get("record_count") or 0),
            }
            for file_record in files
            if isinstance(file_record, dict)
        }
        presets.append(
            {
                "preset": result.get("preset"),
                "domain_adapter": result.get("domain_adapter"),
                "output_label": result.get("output_label"),
                "score": score.get("score") if isinstance(score, dict) else None,
                "gate_passed": score.get("gate", {}).get("passed") if isinstance(score, dict) else None,
                "conversion_status": result.get("conversion", {}).get("status")
                if isinstance(result.get("conversion"), dict)
                else None,
                "metrics": {
                    key: metrics.get(key)
                    for key in (
                        "actionable_warning_count",
                        "retrieval_chunk_record_count",
                        "retrieval_chunk_over_target_count",
                        "domain_unit_record_count",
                        "technical_table_record_count",
                        "requirement_traceability_record_count",
                        "rag_table_record_count",
                        "figure_rag_record_count",
                        "validation_error_count",
                        "validation_warning_count",
                        "ssd_contract_passed",
                    )
                    if isinstance(metrics, dict) and key in metrics
                },
                "artifacts": file_summary,
                "image_asset_count": artifacts.get("image_asset_count") if isinstance(artifacts, dict) else None,
            }
        )
    metric_deltas: list[dict[str, Any]] = []
    if len(presets) >= 2:
        baseline = presets[0]
        for current in presets[1:]:
            baseline_metrics = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
            current_metrics = current.get("metrics") if isinstance(current.get("metrics"), dict) else {}
            for metric in sorted(set(baseline_metrics) | set(current_metrics)):
                left = baseline_metrics.get(metric)
                right = current_metrics.get(metric)
                delta = right - left if isinstance(left, (int, float)) and isinstance(right, (int, float)) else None
                metric_deltas.append(
                    {
                        "metric": metric,
                        "left_preset": baseline.get("preset"),
                        "left_value": left,
                        "right_preset": current.get("preset"),
                        "right_value": right,
                        "delta": delta,
                    }
                )
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": "sanitized_preset_artifact_comparison",
        "presets": presets,
        "metric_deltas": metric_deltas,
    }


def render_scorecard(report: dict[str, Any]) -> str:
    lines = [
        "# Preset Evaluation Scorecard",
        "",
        "| Preset | Domain Adapter | Score | Gate | Status | Actionable Warnings | Chunks | Domain Units | Technical Tables |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for result in report.get("results", []):
        if not isinstance(result, dict):
            continue
        score = result.get("score") if isinstance(result.get("score"), dict) else {}
        metrics = score.get("metrics") if isinstance(score, dict) else {}
        gate = score.get("gate") if isinstance(score, dict) else {}
        conversion = result.get("conversion") if isinstance(result.get("conversion"), dict) else {}
        lines.append(
            "| {preset} | {domain} | {score} | {gate} | {status} | {warnings} | {chunks} | {domains} | {tables} |".format(
                preset=result.get("preset", ""),
                domain=result.get("domain_adapter", NONE_DOMAIN_ADAPTER),
                score=score.get("score", ""),
                gate="pass" if gate.get("passed") else "fail",
                status=conversion.get("status", ""),
                warnings=metrics.get("actionable_warning_count", 0),
                chunks=metrics.get("retrieval_chunk_record_count", 0),
                domains=metrics.get("domain_unit_record_count", 0),
                tables=metrics.get("technical_table_record_count", 0),
            )
        )
    lines.extend(["", "## Failed Gate Conditions", ""])
    failed_any = False
    for result in report.get("results", []):
        if not isinstance(result, dict):
            continue
        score = result.get("score") if isinstance(result.get("score"), dict) else {}
        gate = score.get("gate") if isinstance(score, dict) else {}
        failed_conditions = gate.get("failed_conditions") if isinstance(gate, dict) else []
        if not failed_conditions:
            continue
        failed_any = True
        for condition in failed_conditions:
            if isinstance(condition, dict):
                lines.append(
                    f"- {result.get('preset')}: {condition.get('code')} "
                    f"(actual={condition.get('actual')}, expected={condition.get('expected')})"
                )
    if not failed_any:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def run_preset_eval(config: PresetEvalConfig) -> dict[str, Any]:
    config.output_root.mkdir(parents=True, exist_ok=True)
    source_sha256 = _sha256(config.input_pdf)
    results = [
        evaluate_one_preset(config=config, preset=preset, source_sha256=source_sha256)
        for preset in config.presets
    ]
    comparison = build_preset_artifact_comparison(results)
    report = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "gui_preset_score_gate_evaluation",
        "input_pdf_name": config.input_pdf.name,
        "source_sha256": source_sha256,
        "output_root": ".",
        "presets": list(config.presets),
        "domain_adapter": config.domain_adapter,
        "pages": config.pages,
        "min_score": config.min_score,
        "summary": {
            "preset_count": len(results),
            "passed_gate_count": sum(1 for result in results if result["score"]["gate"]["passed"]),
            "failed_gate_count": sum(1 for result in results if not result["score"]["gate"]["passed"]),
            "passed": all(result["score"]["gate"]["passed"] for result in results),
        },
        "results": results,
    }
    write_json(config.output_root / REPORT_FILENAME, report)
    write_json(config.output_root / COMPARISON_FILENAME, comparison)
    write_text(config.output_root / SCORECARD_FILENAME, render_scorecard(report))
    return report


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _build_thresholds(args: argparse.Namespace) -> dict[str, float]:
    return {
        key: value
        for key, value in {
            "min_hit_at_k": args.min_hit_at_k,
            "min_mrr": args.min_mrr,
            "min_expected_source_coverage": args.min_expected_source_coverage,
            "min_requirement_coverage": args.min_requirement_coverage,
            "min_table_field_coverage": args.min_table_field_coverage,
            "min_cross_ref_resolved_coverage": args.min_cross_ref_resolved_coverage,
            "min_source_ref_presence_coverage": args.min_source_ref_presence_coverage,
            "min_relationship_target_coverage": args.min_relationship_target_coverage,
            "max_chunk_token_p95": args.max_chunk_token_p95,
            "max_chunk_token_max": args.max_chunk_token_max,
            "max_conversion_duration_ms": args.max_conversion_duration_ms,
        }.items()
        if value is not None
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local GUI preset conversion evaluation and score gates.")
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--presets", default=",".join(DEFAULT_PRESETS))
    parser.add_argument(
        "--domain-adapter",
        default=NONE_DOMAIN_ADAPTER,
        choices=[mode.value for mode in DomainAdapterMode],
        help="Domain adapter applied to technical_spec_rag preset outputs.",
    )
    parser.add_argument("--pages", help="Optional pdf2md page range, for example 1-5.")
    parser.add_argument("--rag-eval-set", type=Path)
    parser.add_argument("--rag-top-k", type=int, default=5)
    parser.add_argument("--min-score", type=float)
    parser.add_argument("--fail-on-threshold", action="store_true")
    parser.add_argument("--min-hit-at-k", type=float)
    parser.add_argument("--min-mrr", type=float)
    parser.add_argument("--min-expected-source-coverage", type=float)
    parser.add_argument("--min-requirement-coverage", type=float)
    parser.add_argument("--min-table-field-coverage", type=float)
    parser.add_argument("--min-cross-ref-resolved-coverage", type=float)
    parser.add_argument("--min-source-ref-presence-coverage", type=float)
    parser.add_argument("--min-relationship-target-coverage", type=float)
    parser.add_argument("--max-chunk-token-p95", type=float)
    parser.add_argument("--max-chunk-token-max", type=float)
    parser.add_argument("--max-conversion-duration-ms", type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    presets = _split_csv(args.presets)
    unknown_presets = [preset for preset in presets if preset not in SUPPORTED_RAG_PURPOSE_PROFILES]
    if unknown_presets:
        print(f"Unknown preset(s): {', '.join(unknown_presets)}", file=sys.stderr)
        return 2
    if not args.input_pdf.exists():
        print(f"Input PDF does not exist: {args.input_pdf}", file=sys.stderr)
        return 2
    if args.rag_eval_set is not None and not args.rag_eval_set.exists():
        print(f"RAG eval set does not exist: {args.rag_eval_set}", file=sys.stderr)
        return 2
    report = run_preset_eval(
        PresetEvalConfig(
            input_pdf=args.input_pdf,
            output_root=args.output_root,
            presets=presets,
            domain_adapter=args.domain_adapter,
            pages=args.pages,
            rag_eval_set=args.rag_eval_set,
            rag_top_k=args.rag_top_k,
            rag_thresholds=_build_thresholds(args),
            min_score=args.min_score,
            fail_on_threshold=args.fail_on_threshold,
        )
    )
    print(f"Wrote {args.output_root / REPORT_FILENAME}")
    return 0 if report["summary"]["passed"] or not args.fail_on_threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
