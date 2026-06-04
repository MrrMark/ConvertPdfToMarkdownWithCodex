#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.utils.io import write_json


DEFAULT_GATES = ("ocr", "corpus", "benchmark", "schema", "packaging")
OPTIONAL_GATES = (
    "ci-lightweight",
    "dependency-audit",
    "ocr-backends",
    "rag",
    "index-contract",
    "provenance-integrity",
    "artifact-integrity",
    "preset-eval",
    "docling",
    "figure-description-eval",
    "gui",
    "gui-parity",
    "gui-benchmark",
)
KNOWN_GATES = DEFAULT_GATES + OPTIONAL_GATES


@dataclass(frozen=True)
class ReleaseGateConfig:
    output_dir: Path
    gates: list[str]
    ocr_lang: str = "eng"
    ocr_backend_probe_backends: str = "all"
    ocr_backend_probe_require_ready: bool = True
    corpus_input_dir: Path = Path("pdf")
    corpus_baseline_report: Path | None = None
    benchmark_baseline_report: Path | None = None
    benchmark_page_counts: str = "10,50,100"
    benchmark_page_workers: str = "1"
    max_partial_rate: float | None = None
    max_low_quality_table_rate: float | None = None
    corpus_min_pages_per_second: float | None = None
    max_duration_regression: float = 0.2
    max_memory_regression: float = 0.2
    benchmark_min_pages_per_second: float | None = None
    rag_output_dir: Path | None = None
    rag_eval_set: Path | None = None
    rag_top_k: int = 5
    rag_calibration_profile: Path | None = None
    rag_profile_name: str | None = None
    rag_min_hit_at_k: float | None = None
    rag_min_mrr: float | None = None
    rag_min_citation_coverage: float | None = None
    rag_min_expected_source_coverage: float | None = None
    rag_min_requirement_coverage: float | None = None
    rag_min_table_field_coverage: float | None = None
    rag_min_cross_ref_resolved_coverage: float | None = None
    rag_min_source_ref_presence_coverage: float | None = None
    rag_min_relationship_target_coverage: float | None = None
    rag_max_chunk_token_p95: float | None = None
    rag_max_chunk_token_max: float | None = None
    rag_max_conversion_duration_ms: float | None = None
    index_contract_output_dir: Path | None = None
    index_contract_target: str = "all"
    index_contract_metadata_max_bytes: int | None = None
    index_contract_confidential_safe: bool = False
    index_contract_fail_on_warning: bool = False
    provenance_integrity_output_dir: Path | None = None
    provenance_integrity_fail_on_warning: bool = False
    artifact_integrity_output_dir: Path | None = None
    artifact_integrity_confidential_safe: bool = False
    artifact_integrity_fail_on_warning: bool = False
    preset_eval_input_pdf: Path | None = None
    preset_eval_output_root: Path | None = None
    preset_eval_presets: str = "rag_optimized,technical_spec_rag"
    preset_eval_domain_adapter: str = "none"
    preset_eval_pages: str | None = None
    preset_eval_rag_eval_set: Path | None = None
    preset_eval_min_score: float | None = None
    docling_input_pdf: Path | None = None
    docling_pages: str | None = None
    docling_document_label: str = "nvme-nvm-command-set-rev-1.2-2025-08-01"
    docling_figure_semantics_mode: str = "visual"
    docling_figure_description_backend: str = "local-vlm"
    docling_layout_comparison_mode: str = "summary"
    figure_description_eval_output_dir: Path | None = None
    figure_description_eval_min_confidence: float = 0.65


def _split_gates(raw_gates: str) -> list[str]:
    gates: list[str] = []
    seen: set[str] = set()
    for raw_gate in raw_gates.split(","):
        gate = raw_gate.strip()
        if not gate or gate in seen:
            continue
        if gate not in KNOWN_GATES:
            raise ValueError(f"Unknown release gate: {gate}")
        gates.append(gate)
        seen.add(gate)
    return gates


def _tail(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _run_command(
    *,
    gate: str,
    command: list[str],
    report_path: Path | None = None,
    cwd: Path = Path("."),
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "gate": gate,
        "command": command,
        "exit_code": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "report_path": str(report_path) if report_path is not None else None,
        "stdout_tail": _tail(completed.stdout or ""),
        "stderr_tail": _tail(completed.stderr or ""),
    }


def _as_advisory_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **record,
        "status": "passed",
        "advisory": True,
        "advisory_exit_code": record["exit_code"],
        "advisory_status": record["status"],
    }


def _gui_python_executable() -> str:
    if importlib.util.find_spec("tkinter") is not None and importlib.util.find_spec("_tkinter") is not None:
        return sys.executable
    return shutil.which("python3") or shutil.which("python") or sys.executable


def _write_command_report(record: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        report_path,
        {
            "schema_version": "1.0",
            "gate": record["gate"],
            "command": record["command"],
            "exit_code": record["exit_code"],
            "status": record["status"],
            "stdout_tail": record["stdout_tail"],
            "stderr_tail": record["stderr_tail"],
        },
    )


def _write_ocr_report(record: dict[str, Any], report_path: Path) -> None:
    try:
        payload = json.loads(record.get("stdout_tail") or "{}")
    except json.JSONDecodeError:
        payload = {
            "ready": False,
            "raw_stdout": record.get("stdout_tail", ""),
            "raw_stderr": record.get("stderr_tail", ""),
        }
    write_json(report_path, payload)


def _ocr_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "ocr_runtime_report.json"
    record = _run_command(
        gate="ocr",
        command=[
            sys.executable,
            "scripts/check_ocr_runtime.py",
            "--ocr-lang",
            config.ocr_lang,
            "--json",
        ],
        report_path=report_path,
    )
    _write_ocr_report(record, report_path)
    return [record]


def _ocr_backends_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "ocr_backend_probe_report.json"
    command = [
        sys.executable,
        "scripts/probe_ocr_backends.py",
        "--ocr-lang",
        config.ocr_lang,
        "--backends",
        config.ocr_backend_probe_backends,
        "--report-file",
        str(report_path),
        "--json",
    ]
    if config.ocr_backend_probe_require_ready:
        command.append("--require-ready")
    return [_run_command(gate="ocr-backends", command=command, report_path=report_path)]


def _corpus_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_dir = config.output_dir / "corpus"
    report_path = output_dir / "corpus_eval_report.json"
    command = [
        sys.executable,
        "scripts/run_corpus_eval.py",
        "--input-dir",
        str(config.corpus_input_dir),
        "--output-dir",
        str(output_dir),
        "--fail-on-regression",
    ]
    if config.corpus_baseline_report is not None:
        command.extend(["--baseline-report", str(config.corpus_baseline_report)])
    if config.max_partial_rate is not None:
        command.extend(["--max-partial-rate", str(config.max_partial_rate)])
    if config.max_low_quality_table_rate is not None:
        command.extend(["--max-low-quality-table-rate", str(config.max_low_quality_table_rate)])
    if config.corpus_min_pages_per_second is not None:
        command.extend(["--min-pages-per-second", str(config.corpus_min_pages_per_second)])
    return [_run_command(gate="corpus", command=command, report_path=report_path)]


def _benchmark_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_dir = config.output_dir / "benchmark"
    report_path = output_dir / "benchmark_report.json"
    command = [
        sys.executable,
        "scripts/benchmark_conversion.py",
        "--output-dir",
        str(output_dir),
        "--page-counts",
        config.benchmark_page_counts,
        "--page-workers",
        config.benchmark_page_workers,
        "--fail-on-regression",
        "--max-duration-regression",
        str(config.max_duration_regression),
        "--max-memory-regression",
        str(config.max_memory_regression),
    ]
    if config.benchmark_baseline_report is not None:
        command.extend(["--baseline-report", str(config.benchmark_baseline_report)])
    if config.benchmark_min_pages_per_second is not None:
        command.extend(["--min-pages-per-second", str(config.benchmark_min_pages_per_second)])
    return [_run_command(gate="benchmark", command=command, report_path=report_path)]


def _append_optional_arg(command: list[str], flag: str, value: object | None) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def _rag_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "rag_eval_report.json"
    if config.rag_output_dir is None or config.rag_eval_set is None:
        return [
            {
                "gate": "rag",
                "command": [],
                "exit_code": 2,
                "status": "failed",
                "report_path": str(report_path),
                "stdout_tail": "",
                "stderr_tail": "--rag-output-dir and --rag-eval-set are required when --gates includes rag.",
            }
        ]
    command = [
        sys.executable,
        "scripts/run_rag_eval.py",
        "--output-dir",
        str(config.rag_output_dir),
        "--eval-set",
        str(config.rag_eval_set),
        "--top-k",
        str(config.rag_top_k),
        "--report-path",
        str(report_path),
        "--fail-on-threshold",
    ]
    _append_optional_arg(command, "--calibration-profile", config.rag_calibration_profile)
    _append_optional_arg(command, "--profile-name", config.rag_profile_name)
    _append_optional_arg(command, "--min-hit-at-k", config.rag_min_hit_at_k)
    _append_optional_arg(command, "--min-mrr", config.rag_min_mrr)
    _append_optional_arg(command, "--min-citation-coverage", config.rag_min_citation_coverage)
    _append_optional_arg(command, "--min-expected-source-coverage", config.rag_min_expected_source_coverage)
    _append_optional_arg(command, "--min-requirement-coverage", config.rag_min_requirement_coverage)
    _append_optional_arg(command, "--min-table-field-coverage", config.rag_min_table_field_coverage)
    _append_optional_arg(command, "--min-cross-ref-resolved-coverage", config.rag_min_cross_ref_resolved_coverage)
    _append_optional_arg(command, "--min-source-ref-presence-coverage", config.rag_min_source_ref_presence_coverage)
    _append_optional_arg(command, "--min-relationship-target-coverage", config.rag_min_relationship_target_coverage)
    _append_optional_arg(command, "--max-chunk-token-p95", config.rag_max_chunk_token_p95)
    _append_optional_arg(command, "--max-chunk-token-max", config.rag_max_chunk_token_max)
    _append_optional_arg(command, "--max-conversion-duration-ms", config.rag_max_conversion_duration_ms)
    return [_run_command(gate="rag", command=command, report_path=report_path)]


def _index_contract_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "index_contract_report.json"
    if config.index_contract_output_dir is None:
        return [
            {
                "gate": "index-contract",
                "command": [],
                "exit_code": 2,
                "status": "failed",
                "report_path": str(report_path),
                "stdout_tail": "",
                "stderr_tail": "--index-contract-output-dir is required when --gates includes index-contract.",
            }
        ]
    command = [
        sys.executable,
        "scripts/validate_index_contract.py",
        "--output-dir",
        str(config.index_contract_output_dir),
        "--target",
        config.index_contract_target,
        "--report-file",
        str(report_path),
        "--fail-on-error",
    ]
    _append_optional_arg(command, "--metadata-max-bytes", config.index_contract_metadata_max_bytes)
    if config.index_contract_confidential_safe:
        command.append("--confidential-safe")
    if config.index_contract_fail_on_warning:
        command.append("--fail-on-warning")
    return [_run_command(gate="index-contract", command=command, report_path=report_path)]


def _provenance_integrity_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "provenance_integrity_report.json"
    if config.provenance_integrity_output_dir is None:
        return [
            {
                "gate": "provenance-integrity",
                "command": [],
                "exit_code": 2,
                "status": "failed",
                "report_path": str(report_path),
                "stdout_tail": "",
                "stderr_tail": "--provenance-integrity-output-dir is required when --gates includes provenance-integrity.",
            }
        ]
    command = [
        sys.executable,
        "scripts/validate_provenance_integrity.py",
        "--output-dir",
        str(config.provenance_integrity_output_dir),
        "--report-file",
        str(report_path),
        "--fail-on-error",
    ]
    if config.provenance_integrity_fail_on_warning:
        command.append("--fail-on-warning")
    return [_run_command(gate="provenance-integrity", command=command, report_path=report_path)]


def _artifact_integrity_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "artifact_integrity_report.json"
    if config.artifact_integrity_output_dir is None:
        return [
            {
                "gate": "artifact-integrity",
                "command": [],
                "exit_code": 2,
                "status": "failed",
                "report_path": str(report_path),
                "stdout_tail": "",
                "stderr_tail": "--artifact-integrity-output-dir is required when --gates includes artifact-integrity.",
            }
        ]
    command = [
        sys.executable,
        "scripts/validate_artifact_integrity.py",
        "--output-dir",
        str(config.artifact_integrity_output_dir),
        "--report-file",
        str(report_path),
        "--fail-on-error",
    ]
    if config.artifact_integrity_confidential_safe:
        command.append("--confidential-safe")
    if config.artifact_integrity_fail_on_warning:
        command.append("--fail-on-warning")
    return [_run_command(gate="artifact-integrity", command=command, report_path=report_path)]


def _preset_eval_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_root = config.preset_eval_output_root or (config.output_dir / "preset-eval")
    report_path = output_root / "preset_eval_report.json"
    if config.preset_eval_input_pdf is None:
        return [
            {
                "gate": "preset-eval",
                "command": [],
                "exit_code": 2,
                "status": "failed",
                "report_path": str(report_path),
                "stdout_tail": "",
                "stderr_tail": "--preset-eval-input-pdf is required when --gates includes preset-eval.",
            }
        ]
    command = [
        sys.executable,
        "scripts/run_preset_eval.py",
        "--input-pdf",
        str(config.preset_eval_input_pdf),
        "--output-root",
        str(output_root),
        "--presets",
        config.preset_eval_presets,
        "--domain-adapter",
        config.preset_eval_domain_adapter,
        "--fail-on-threshold",
    ]
    _append_optional_arg(command, "--pages", config.preset_eval_pages)
    _append_optional_arg(command, "--rag-eval-set", config.preset_eval_rag_eval_set)
    _append_optional_arg(command, "--rag-top-k", config.rag_top_k)
    _append_optional_arg(command, "--min-score", config.preset_eval_min_score)
    _append_optional_arg(command, "--min-hit-at-k", config.rag_min_hit_at_k)
    _append_optional_arg(command, "--min-mrr", config.rag_min_mrr)
    _append_optional_arg(command, "--min-expected-source-coverage", config.rag_min_expected_source_coverage)
    _append_optional_arg(command, "--min-requirement-coverage", config.rag_min_requirement_coverage)
    _append_optional_arg(command, "--min-table-field-coverage", config.rag_min_table_field_coverage)
    _append_optional_arg(command, "--min-cross-ref-resolved-coverage", config.rag_min_cross_ref_resolved_coverage)
    _append_optional_arg(command, "--min-source-ref-presence-coverage", config.rag_min_source_ref_presence_coverage)
    _append_optional_arg(command, "--min-relationship-target-coverage", config.rag_min_relationship_target_coverage)
    _append_optional_arg(command, "--max-chunk-token-p95", config.rag_max_chunk_token_p95)
    _append_optional_arg(command, "--max-chunk-token-max", config.rag_max_chunk_token_max)
    _append_optional_arg(command, "--max-conversion-duration-ms", config.rag_max_conversion_duration_ms)
    return [_run_command(gate="preset-eval", command=command, report_path=report_path)]


def _docling_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_dir = config.output_dir / "docling"
    report_path = output_dir / "docling_benchmark_report.json"
    if config.docling_input_pdf is None:
        return [
            {
                "gate": "docling",
                "command": [],
                "exit_code": 2,
                "status": "failed",
                "report_path": str(report_path),
                "stdout_tail": "",
                "stderr_tail": "--docling-input-pdf is required when --gates includes docling.",
            }
        ]
    command = [
        sys.executable,
        "scripts/run_latest_nvme_command_set_eval.py",
        "--input-pdf",
        str(config.docling_input_pdf),
        "--output-dir",
        str(output_dir),
        "--document-label",
        config.docling_document_label,
        "--figure-semantics-mode",
        config.docling_figure_semantics_mode,
        "--figure-description-backend",
        config.docling_figure_description_backend,
        "--layout-comparison-mode",
        config.docling_layout_comparison_mode,
        "--require-docling",
        "--fail-on-error",
        "--fail-on-current-tool-failure",
    ]
    _append_optional_arg(command, "--pages", config.docling_pages)
    return [_run_command(gate="docling", command=command, report_path=report_path)]


def _figure_description_eval_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "figure_description_eval_report.json"
    if config.figure_description_eval_output_dir is None:
        return [
            {
                "gate": "figure-description-eval",
                "command": [],
                "exit_code": 2,
                "status": "failed",
                "report_path": str(report_path),
                "stdout_tail": "",
                "stderr_tail": (
                    "--figure-description-eval-output-dir is required when "
                    "--gates includes figure-description-eval."
                ),
            }
        ]
    command = [
        sys.executable,
        "scripts/evaluate_figure_descriptions.py",
        "--output-dir",
        str(config.figure_description_eval_output_dir),
        "--report-file",
        str(report_path),
        "--min-confidence",
        str(config.figure_description_eval_min_confidence),
        "--fail-on-error",
    ]
    return [_run_command(gate="figure-description-eval", command=command, report_path=report_path)]


def _gui_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    gui_python = _gui_python_executable()
    output_dir = config.output_dir / "gui"
    smoke_output_dir = output_dir / "smoke"
    support_output_dir = output_dir / "support"
    smoke_evidence_path = smoke_output_dir / "gui_smoke_evidence.json"
    support_bundle_path = support_output_dir / "gui_support_bundle.json"
    state_path = smoke_output_dir / "gui_state.json"
    records: list[dict[str, Any]] = []

    help_report_path = output_dir / "gui_help_report.json"
    help_record = _run_command(
        gate="gui:module-help",
        command=[gui_python, "-m", "pdf2md.gui", "--help"],
        report_path=help_report_path,
    )
    _write_command_report(help_record, help_report_path)
    records.append(help_record)

    doctor_report_path = output_dir / "gui_doctor_report.json"
    doctor_record = _run_command(
        gate="gui:doctor",
        command=[gui_python, "-m", "pdf2md.gui", "--doctor", "--doctor-format", "json"],
        report_path=doctor_report_path,
    )
    _write_command_report(doctor_record, doctor_report_path)
    records.append(doctor_record)

    records.append(
        _run_command(
            gate="gui:smoke-evidence",
            command=[
                gui_python,
                "scripts/run_gui_smoke_evidence.py",
                "--output-dir",
                str(smoke_output_dir),
                "--state-path",
                str(state_path),
            ],
            report_path=smoke_evidence_path,
        )
    )
    records.append(
        _run_command(
            gate="gui:support-bundle",
            command=[
                gui_python,
                "scripts/create_gui_support_bundle.py",
                "--output-dir",
                str(support_output_dir),
                "--smoke-evidence",
                str(smoke_evidence_path),
            ],
            report_path=support_bundle_path,
        )
    )
    return records


def _gui_parity_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_dir = config.output_dir / "gui-parity"
    report_path = output_dir / "gui_cli_parity_report.json"
    return [
        _run_command(
            gate="gui-parity",
            command=[
                sys.executable,
                "scripts/run_gui_cli_parity.py",
                "--output-dir",
                str(output_dir),
            ],
            report_path=report_path,
        )
    ]


def _gui_benchmark_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_dir = config.output_dir / "gui-benchmark"
    report_path = output_dir / "gui_cli_benchmark_report.json"
    return [
        _run_command(
            gate="gui-benchmark",
            command=[
                sys.executable,
                "scripts/benchmark_gui_cli_parity.py",
                "--output-dir",
                str(output_dir),
            ],
            report_path=report_path,
        )
    ]


def _schema_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    return [
        _run_command(
            gate="schema",
            command=[sys.executable, "scripts/export_output_schema.py", "--check"],
            report_path=Path("docs/schema"),
        )
    ]


def _ci_lightweight_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    return [
        _run_command(
            gate="ci-lightweight:schema",
            command=[sys.executable, "scripts/export_output_schema.py", "--check"],
            report_path=Path("docs/schema"),
        ),
        _run_command(
            gate="ci-lightweight:docs-output-contract",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "tests/test_docs_examples.py",
                "tests/test_output_schema_contract.py",
                "-q",
            ],
            report_path=None,
        ),
        _run_command(
            gate="ci-lightweight:cli-smoke",
            command=[sys.executable, "-m", "pdf2md", "--help"],
            report_path=None,
        ),
        _run_command(
            gate="ci-lightweight:lint-smoke",
            command=[sys.executable, "-m", "ruff", "check", "."],
            report_path=None,
        ),
    ]


def _dependency_audit_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "dependency_audit_report.json"
    cache_dir = config.output_dir / "pip-audit-cache"
    record = _run_command(
        gate="dependency-audit",
        command=[
            sys.executable,
            "-m",
            "pip_audit",
            "--format",
            "json",
            "--output",
            str(report_path),
            "--cache-dir",
            str(cache_dir),
            "--progress-spinner",
            "off",
        ],
        report_path=report_path,
    )
    return [_as_advisory_record(record)]


def _packaging_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    dist_dir = config.output_dir / "dist"
    return [
        _run_command(
            gate="packaging:build",
            command=[
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(dist_dir),
            ],
            report_path=dist_dir,
        ),
        _run_command(
            gate="packaging:wheel-contract",
            command=[
                sys.executable,
                "scripts/inspect_wheel_contract.py",
                "--dist-dir",
                str(dist_dir),
                "--report-file",
                str(dist_dir / "wheel_contract_report.json"),
            ],
            report_path=dist_dir / "wheel_contract_report.json",
        ),
        _run_command(
            gate="packaging:module-help",
            command=[sys.executable, "-m", "pdf2md", "--help"],
            report_path=None,
        ),
        _run_command(
            gate="packaging:gui-module-help",
            command=[_gui_python_executable(), "-m", "pdf2md.gui", "--help"],
            report_path=None,
        ),
    ]


def run_release_gates(config: ReleaseGateConfig) -> dict[str, Any]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for gate in config.gates:
        if gate == "ocr":
            records.extend(_ocr_gate(config))
        elif gate == "ocr-backends":
            records.extend(_ocr_backends_gate(config))
        elif gate == "corpus":
            records.extend(_corpus_gate(config))
        elif gate == "benchmark":
            records.extend(_benchmark_gate(config))
        elif gate == "rag":
            records.extend(_rag_gate(config))
        elif gate == "index-contract":
            records.extend(_index_contract_gate(config))
        elif gate == "provenance-integrity":
            records.extend(_provenance_integrity_gate(config))
        elif gate == "artifact-integrity":
            records.extend(_artifact_integrity_gate(config))
        elif gate == "preset-eval":
            records.extend(_preset_eval_gate(config))
        elif gate == "docling":
            records.extend(_docling_gate(config))
        elif gate == "figure-description-eval":
            records.extend(_figure_description_eval_gate(config))
        elif gate == "gui":
            records.extend(_gui_gate(config))
        elif gate == "gui-parity":
            records.extend(_gui_parity_gate(config))
        elif gate == "gui-benchmark":
            records.extend(_gui_benchmark_gate(config))
        elif gate == "ci-lightweight":
            records.extend(_ci_lightweight_gate(config))
        elif gate == "dependency-audit":
            records.extend(_dependency_audit_gate(config))
        elif gate == "schema":
            records.extend(_schema_gate(config))
        elif gate == "packaging":
            records.extend(_packaging_gate(config))
    failed = [record for record in records if record["status"] != "passed"]
    payload = {
        "schema_version": "1.0",
        "output_dir": str(config.output_dir),
        "gates_requested": config.gates,
        "gates": records,
        "summary": {
            "total_gate_commands": len(records),
            "passed_count": len(records) - len(failed),
            "failed_count": len(failed),
        },
        "passed_release_gate": not failed,
    }
    write_json(config.output_dir / "release_gate_report.json", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pdf2md release gates and write a unified report.")
    parser.add_argument("--output-dir", type=Path, default=Path("release_gate_output"))
    parser.add_argument(
        "--gates",
        default=",".join(DEFAULT_GATES),
        help=(
            "Comma-separated gates: "
            "ocr,corpus,benchmark,schema,packaging,ci-lightweight,dependency-audit,ocr-backends,rag,index-contract,provenance-integrity,"
            "artifact-integrity,preset-eval,docling,figure-description-eval,gui,gui-parity,gui-benchmark."
        ),
    )
    parser.add_argument("--ocr-lang", default="eng")
    parser.add_argument("--ocr-backend-probe-backends", default="all")
    parser.add_argument("--ocr-backend-probe-no-require-ready", action="store_true")
    parser.add_argument("--corpus-input-dir", type=Path, default=Path("pdf"))
    parser.add_argument("--corpus-baseline-report", type=Path)
    parser.add_argument("--benchmark-baseline-report", type=Path)
    parser.add_argument("--benchmark-page-counts", default="10,50,100")
    parser.add_argument("--benchmark-page-workers", default="1")
    parser.add_argument("--max-partial-rate", type=float)
    parser.add_argument("--max-low-quality-table-rate", type=float)
    parser.add_argument("--corpus-min-pages-per-second", type=float)
    parser.add_argument("--max-duration-regression", type=float, default=0.2)
    parser.add_argument("--max-memory-regression", type=float, default=0.2)
    parser.add_argument("--benchmark-min-pages-per-second", type=float)
    parser.add_argument("--rag-output-dir", type=Path)
    parser.add_argument("--rag-eval-set", type=Path)
    parser.add_argument("--rag-top-k", type=int, default=5)
    parser.add_argument("--rag-calibration-profile", type=Path)
    parser.add_argument("--rag-profile-name")
    parser.add_argument("--rag-min-hit-at-k", type=float)
    parser.add_argument("--rag-min-mrr", type=float)
    parser.add_argument("--rag-min-citation-coverage", type=float)
    parser.add_argument("--rag-min-expected-source-coverage", type=float)
    parser.add_argument("--rag-min-requirement-coverage", type=float)
    parser.add_argument("--rag-min-table-field-coverage", type=float)
    parser.add_argument("--rag-min-cross-ref-resolved-coverage", type=float)
    parser.add_argument("--rag-min-source-ref-presence-coverage", type=float)
    parser.add_argument("--rag-min-relationship-target-coverage", type=float)
    parser.add_argument("--rag-max-chunk-token-p95", type=float)
    parser.add_argument("--rag-max-chunk-token-max", type=float)
    parser.add_argument("--rag-max-conversion-duration-ms", type=float)
    parser.add_argument("--index-contract-output-dir", type=Path)
    parser.add_argument(
        "--index-contract-target",
        default="all",
        choices=("all", "openai", "azure-ai-search", "langchain", "llamaindex"),
    )
    parser.add_argument("--index-contract-metadata-max-bytes", type=int)
    parser.add_argument("--index-contract-confidential-safe", action="store_true")
    parser.add_argument("--index-contract-fail-on-warning", action="store_true")
    parser.add_argument("--provenance-integrity-output-dir", type=Path)
    parser.add_argument("--provenance-integrity-fail-on-warning", action="store_true")
    parser.add_argument("--artifact-integrity-output-dir", type=Path)
    parser.add_argument("--artifact-integrity-confidential-safe", action="store_true")
    parser.add_argument("--artifact-integrity-fail-on-warning", action="store_true")
    parser.add_argument("--preset-eval-input-pdf", type=Path)
    parser.add_argument("--preset-eval-output-root", type=Path)
    parser.add_argument("--preset-eval-presets", default="rag_optimized,technical_spec_rag")
    parser.add_argument(
        "--preset-eval-domain-adapter",
        default="none",
        choices=("none", "nvme", "pcie", "ocp", "tcg", "spdm", "customer-requirements"),
    )
    parser.add_argument("--preset-eval-pages")
    parser.add_argument("--preset-eval-rag-eval-set", type=Path)
    parser.add_argument("--preset-eval-min-score", type=float)
    parser.add_argument("--docling-input-pdf", type=Path)
    parser.add_argument("--docling-pages")
    parser.add_argument("--docling-document-label", default="nvme-nvm-command-set-rev-1.2-2025-08-01")
    parser.add_argument("--docling-figure-semantics-mode", choices=("assetless", "visual"), default="visual")
    parser.add_argument(
        "--docling-figure-description-backend",
        choices=("local-vlm", "docling"),
        default="local-vlm",
    )
    parser.add_argument("--docling-layout-comparison-mode", choices=("off", "summary"), default="summary")
    parser.add_argument("--figure-description-eval-output-dir", type=Path)
    parser.add_argument("--figure-description-eval-min-confidence", type=float, default=0.65)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        gates = _split_gates(args.gates)
    except ValueError as exc:
        print(str(exc))
        return 2
    payload = run_release_gates(
        ReleaseGateConfig(
            output_dir=args.output_dir,
            gates=gates,
            ocr_lang=args.ocr_lang,
            ocr_backend_probe_backends=args.ocr_backend_probe_backends,
            ocr_backend_probe_require_ready=not args.ocr_backend_probe_no_require_ready,
            corpus_input_dir=args.corpus_input_dir,
            corpus_baseline_report=args.corpus_baseline_report,
            benchmark_baseline_report=args.benchmark_baseline_report,
            benchmark_page_counts=args.benchmark_page_counts,
            benchmark_page_workers=args.benchmark_page_workers,
            max_partial_rate=args.max_partial_rate,
            max_low_quality_table_rate=args.max_low_quality_table_rate,
            corpus_min_pages_per_second=args.corpus_min_pages_per_second,
            max_duration_regression=args.max_duration_regression,
            max_memory_regression=args.max_memory_regression,
            benchmark_min_pages_per_second=args.benchmark_min_pages_per_second,
            rag_output_dir=args.rag_output_dir,
            rag_eval_set=args.rag_eval_set,
            rag_top_k=args.rag_top_k,
            rag_calibration_profile=args.rag_calibration_profile,
            rag_profile_name=args.rag_profile_name,
            rag_min_hit_at_k=args.rag_min_hit_at_k,
            rag_min_mrr=args.rag_min_mrr,
            rag_min_citation_coverage=args.rag_min_citation_coverage,
            rag_min_expected_source_coverage=args.rag_min_expected_source_coverage,
            rag_min_requirement_coverage=args.rag_min_requirement_coverage,
            rag_min_table_field_coverage=args.rag_min_table_field_coverage,
            rag_min_cross_ref_resolved_coverage=args.rag_min_cross_ref_resolved_coverage,
            rag_min_source_ref_presence_coverage=args.rag_min_source_ref_presence_coverage,
            rag_min_relationship_target_coverage=args.rag_min_relationship_target_coverage,
            rag_max_chunk_token_p95=args.rag_max_chunk_token_p95,
            rag_max_chunk_token_max=args.rag_max_chunk_token_max,
            rag_max_conversion_duration_ms=args.rag_max_conversion_duration_ms,
            index_contract_output_dir=args.index_contract_output_dir,
            index_contract_target=args.index_contract_target,
            index_contract_metadata_max_bytes=args.index_contract_metadata_max_bytes,
            index_contract_confidential_safe=args.index_contract_confidential_safe,
            index_contract_fail_on_warning=args.index_contract_fail_on_warning,
            provenance_integrity_output_dir=args.provenance_integrity_output_dir,
            provenance_integrity_fail_on_warning=args.provenance_integrity_fail_on_warning,
            artifact_integrity_output_dir=args.artifact_integrity_output_dir,
            artifact_integrity_confidential_safe=args.artifact_integrity_confidential_safe,
            artifact_integrity_fail_on_warning=args.artifact_integrity_fail_on_warning,
            preset_eval_input_pdf=args.preset_eval_input_pdf,
            preset_eval_output_root=args.preset_eval_output_root,
            preset_eval_presets=args.preset_eval_presets,
            preset_eval_domain_adapter=args.preset_eval_domain_adapter,
            preset_eval_pages=args.preset_eval_pages,
            preset_eval_rag_eval_set=args.preset_eval_rag_eval_set,
            preset_eval_min_score=args.preset_eval_min_score,
            docling_input_pdf=args.docling_input_pdf,
            docling_pages=args.docling_pages,
            docling_document_label=args.docling_document_label,
            docling_figure_semantics_mode=args.docling_figure_semantics_mode,
            docling_figure_description_backend=args.docling_figure_description_backend,
            docling_layout_comparison_mode=args.docling_layout_comparison_mode,
            figure_description_eval_output_dir=args.figure_description_eval_output_dir,
            figure_description_eval_min_confidence=args.figure_description_eval_min_confidence,
        )
    )
    print(f"Wrote {args.output_dir / 'release_gate_report.json'}")
    return 0 if payload["passed_release_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
