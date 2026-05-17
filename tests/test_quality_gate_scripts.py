from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

from scripts import benchmark_conversion
from scripts import benchmark_gui_cli_parity
from scripts import check_ocr_runtime
from scripts import inspect_wheel_contract
from scripts import run_gui_cli_parity
from scripts import run_corpus_eval
from scripts import run_release_gates


def test_corpus_quality_gate_records_baseline_and_threshold_regressions(tmp_path: Path) -> None:
    payload = {
        "summary": {
            "total_documents": 4,
            "success_count": 2,
            "partial_success_count": 2,
            "failed_count": 0,
            "skipped_count": 0,
            "table_fallback_reason_counts": {"complex_table": 2},
            "total_suppressed_lines": 5,
            "table_low_quality_count": 2,
            "table_total": 4,
            "pages_per_second_min": 1.1,
            "pages_per_second_mean": 2.0,
            "pdf_open_count": 8,
            "text_line_extract_count": 20,
        }
    }
    baseline = {
        "summary": {
            "success_count": 3,
            "partial_success_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
            "table_fallback_reason_counts": {"complex_table": 1},
            "total_suppressed_lines": 4,
            "table_low_quality_count": 1,
            "pages_per_second_min": 1.5,
            "pages_per_second_mean": 2.2,
            "pdf_open_count": 6,
            "text_line_extract_count": 18,
        }
    }

    result = run_corpus_eval.apply_quality_gate(
        payload,
        baseline_report=baseline,
        baseline_report_path=tmp_path / "baseline.json",
        max_partial_rate=0.25,
        max_low_quality_table_rate=0.25,
        min_pages_per_second=1.2,
    )

    metrics = {item["metric"] for item in result["regressions"]}
    assert result["passed_quality_gate"] is False
    assert result["baseline_report"].endswith("baseline.json")
    assert result["summary"]["partial_success_rate"] == 0.5
    assert result["summary"]["low_quality_table_rate"] == 0.5
    assert "summary.success_count" in metrics
    assert "summary.table_fallback_reason_counts.complex_table" in metrics
    assert "summary.partial_success_rate" in metrics
    assert "summary.pages_per_second_min" in metrics


def test_corpus_quality_gate_passes_without_baseline_or_threshold_failures() -> None:
    payload = {
        "summary": {
            "total_documents": 1,
            "success_count": 1,
            "partial_success_count": 0,
            "table_low_quality_count": 0,
            "table_total": 0,
            "pages_per_second_min": 3.0,
        }
    }

    result = run_corpus_eval.apply_quality_gate(payload, min_pages_per_second=2.0)

    assert result["passed_quality_gate"] is True
    assert result["baseline_report"] is None
    assert result["regressions"] == []


def test_benchmark_performance_gate_records_page_count_regressions(tmp_path: Path) -> None:
    payload = {
        "runs": [
            {
                "page_count": 10,
                "elapsed_ms": 1300,
                "total_duration_ms": 1300,
                "peak_memory_bytes": 1500,
                "stage_durations_ms": {"text": 500},
                "pages_per_second": 7.5,
                "pdf_open_count": 3,
                "text_line_extract_count": 25,
            }
        ]
    }
    baseline = {
        "runs": [
            {
                "page_count": 10,
                "total_duration_ms": 1000,
                "peak_memory_bytes": 1000,
                "stage_durations_ms": {"text": 300},
                "pages_per_second": 10.0,
                "pdf_open_count": 2,
                "text_line_extract_count": 20,
            }
        ]
    }

    result = benchmark_conversion.apply_performance_gate(
        payload,
        baseline_report=baseline,
        baseline_report_path=tmp_path / "benchmark_report.json",
        max_duration_regression=0.2,
        max_memory_regression=0.2,
        min_pages_per_second=8.0,
    )

    metrics = {item["metric"] for item in result["regressions"]}
    assert result["passed_performance_gate"] is False
    assert result["baseline_report"].endswith("benchmark_report.json")
    assert "total_duration_ms" in metrics
    assert "peak_memory_bytes" in metrics
    assert "stage_durations_ms.text" in metrics
    assert "pages_per_second" in metrics
    assert "pdf_open_count" in metrics
    assert "text_line_extract_count" in metrics


def test_benchmark_performance_gate_records_worker_equivalence_failures() -> None:
    payload = {
        "runs": [],
        "worker_equivalence": {
            "mismatches": [
                {
                    "page_count": 10,
                    "baseline_page_workers": 1,
                    "page_workers": 2,
                    "different_artifacts": ["tables_rag.jsonl"],
                }
            ],
            "passed": False,
        },
    }

    result = benchmark_conversion.apply_performance_gate(payload)

    assert result["passed_performance_gate"] is False
    assert result["regressions"][0]["type"] == "worker_equivalence_failure"
    assert result["regressions"][0]["metric"] == "worker_output_hashes"
    assert result["regressions"][0]["different_artifacts"] == ["tables_rag.jsonl"]


def test_ocr_runtime_check_reports_missing_tesseract(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(check_ocr_runtime, "_discover_tesseract", lambda: None)
    monkeypatch.setattr(check_ocr_runtime, "_module_available", lambda module_name: module_name == "pytesseract")

    report = check_ocr_runtime.check_ocr_runtime("kor+eng")
    text = check_ocr_runtime.format_text_report(report)

    assert report["ready"] is False
    assert report["checks"]["tesseract_executable"]["ok"] is False
    assert report["checks"]["pypdfium2_import"]["ok"] is False
    assert report["checks"]["language_data"]["missing"] == ["kor", "eng"]
    assert "Tesseract executable: MISSING" in text


def test_ocr_runtime_check_identifies_missing_composite_language(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(check_ocr_runtime, "_discover_tesseract", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr(check_ocr_runtime, "_module_available", lambda module_name: True)
    monkeypatch.setattr(check_ocr_runtime, "_list_tesseract_languages", lambda executable: (["eng"], None))

    report = check_ocr_runtime.check_ocr_runtime("kor+eng")

    assert report["ready"] is False
    assert report["checks"]["language_data"]["requested"] == ["kor", "eng"]
    assert report["checks"]["language_data"]["missing"] == ["kor"]


def test_release_gate_runner_writes_success_summary(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        stdout = '{"ready": true}' if any(str(part).endswith("check_ocr_runtime.py") for part in command) else "ok"
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release",
            gates=["ocr", "corpus", "benchmark", "schema", "packaging"],
            corpus_input_dir=Path("pdf"),
            corpus_baseline_report=Path("pdf/baseline/corpus_eval_report.json"),
            benchmark_baseline_report=Path("pdf/baseline/benchmark_report.json"),
            benchmark_page_counts="10",
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 8
    assert (tmp_path / "release" / "release_gate_report.json").exists()
    assert (tmp_path / "release" / "ocr_runtime_report.json").exists()
    assert any(any(str(part).endswith("run_corpus_eval.py") for part in command) for command in calls)
    assert any(any(str(part).endswith("benchmark_conversion.py") for part in command) for command in calls)
    assert any(any(str(part).endswith("export_output_schema.py") for part in command) for command in calls)
    assert any(any(str(part).endswith("inspect_wheel_contract.py") for part in command) for command in calls)
    assert any(command[1:] == ["-m", "pdf2md.gui", "--help"] for command in calls)
    benchmark_command = next(command for command in calls if any(str(part).endswith("benchmark_conversion.py") for part in command))
    assert "--page-workers" in benchmark_command


def test_release_gate_runner_fails_when_any_gate_command_fails(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(command, **kwargs):  # noqa: ANN001
        returncode = 1 if any(str(part).endswith("benchmark_conversion.py") for part in command) else 0
        stdout = '{"ready": true}' if any(str(part).endswith("check_ocr_runtime.py") for part in command) else ""
        stderr = "benchmark failed" if returncode else ""
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-fail",
            gates=["ocr", "benchmark"],
            benchmark_page_counts="10",
        )
    )

    assert payload["passed_release_gate"] is False
    assert payload["summary"]["failed_count"] == 1
    failed = [record for record in payload["gates"] if record["status"] == "failed"]
    assert failed[0]["gate"] == "benchmark"
    assert "benchmark failed" in failed[0]["stderr_tail"]


def test_release_gate_runner_supports_optional_rag_calibration_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote rag_eval_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-rag",
            gates=["rag"],
            rag_output_dir=tmp_path / "converted-spec",
            rag_eval_set=tmp_path / "rag_eval_queries.json",
            rag_min_expected_source_coverage=0.9,
            rag_min_requirement_coverage=0.9,
            rag_min_table_field_coverage=0.85,
            rag_min_cross_ref_resolved_coverage=0.8,
            rag_max_chunk_token_p95=512,
            rag_max_conversion_duration_ms=10_000,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "rag"
    command = calls[0]
    assert any(str(part).endswith("run_rag_eval.py") for part in command)
    assert "--fail-on-threshold" in command
    assert "--min-expected-source-coverage" in command
    assert "--min-requirement-coverage" in command
    assert "--max-conversion-duration-ms" in command


def test_release_gate_runner_supports_optional_index_contract_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote index_contract_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-index",
            gates=["index-contract"],
            index_contract_output_dir=tmp_path / "converted-spec",
            index_contract_target="azure-ai-search",
            index_contract_metadata_max_bytes=2048,
            index_contract_confidential_safe=True,
            index_contract_fail_on_warning=True,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "index-contract"
    command = calls[0]
    assert any(str(part).endswith("validate_index_contract.py") for part in command)
    assert "--target" in command
    assert "azure-ai-search" in command
    assert "--metadata-max-bytes" in command
    assert "--confidential-safe" in command
    assert "--fail-on-warning" in command


def test_release_gate_runner_supports_optional_provenance_integrity_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote provenance_integrity_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-provenance",
            gates=["provenance-integrity"],
            provenance_integrity_output_dir=tmp_path / "converted-spec",
            provenance_integrity_fail_on_warning=True,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "provenance-integrity"
    command = calls[0]
    assert any(str(part).endswith("validate_provenance_integrity.py") for part in command)
    assert "--output-dir" in command
    assert "--fail-on-error" in command
    assert "--fail-on-warning" in command


def test_release_gate_runner_supports_optional_artifact_integrity_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote artifact_integrity_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-artifacts",
            gates=["artifact-integrity"],
            artifact_integrity_output_dir=tmp_path / "converted-spec",
            artifact_integrity_confidential_safe=True,
            artifact_integrity_fail_on_warning=True,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "artifact-integrity"
    command = calls[0]
    assert any(str(part).endswith("validate_artifact_integrity.py") for part in command)
    assert "--output-dir" in command
    assert "--fail-on-error" in command
    assert "--confidential-safe" in command
    assert "--fail-on-warning" in command


def test_release_gate_runner_supports_optional_gui_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        stdout = '{"kind": "gui_runtime_doctor", "passed": true}' if "--doctor" in command else "ok"
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui",
            gates=["gui"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 4
    assert [record["gate"] for record in payload["gates"]] == [
        "gui:module-help",
        "gui:doctor",
        "gui:smoke-evidence",
        "gui:support-bundle",
    ]
    assert (tmp_path / "release-gui" / "gui" / "gui_help_report.json").exists()
    assert (tmp_path / "release-gui" / "gui" / "gui_doctor_report.json").exists()
    assert any(command[1:] == ["-m", "pdf2md.gui", "--help"] for command in calls)
    assert any("--doctor-format" in command and "json" in command for command in calls)
    smoke_command = next(command for command in calls if any(str(part).endswith("run_gui_smoke_evidence.py") for part in command))
    support_command = next(command for command in calls if any(str(part).endswith("create_gui_support_bundle.py") for part in command))
    assert "--state-path" in smoke_command
    assert str(tmp_path / "release-gui" / "gui" / "smoke") in smoke_command
    assert "--smoke-evidence" in support_command
    assert str(tmp_path / "release-gui" / "gui" / "smoke" / "gui_smoke_evidence.json") in support_command
    assert payload["gates"][2]["report_path"].endswith("gui_smoke_evidence.json")
    assert payload["gates"][3]["report_path"].endswith("gui_support_bundle.json")


def test_release_gate_runner_fails_gui_gate_on_redaction_failure(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(command, **kwargs):  # noqa: ANN001
        if any(str(part).endswith("run_gui_smoke_evidence.py") for part in command):
            return SimpleNamespace(returncode=1, stdout="", stderr="redaction failed")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui-redaction-fail",
            gates=["gui"],
        )
    )

    assert payload["passed_release_gate"] is False
    assert payload["summary"]["failed_count"] == 1
    failed = [record for record in payload["gates"] if record["status"] == "failed"]
    assert failed[0]["gate"] == "gui:smoke-evidence"
    assert "redaction failed" in failed[0]["stderr_tail"]


def test_gui_cli_parity_report_detects_hash_mismatch(tmp_path: Path) -> None:
    cli_output = tmp_path / "cli"
    gui_output = tmp_path / "gui"
    cli_output.mkdir()
    gui_output.mkdir()
    (cli_output / "document.md").write_text("cli\n", encoding="utf-8")
    (gui_output / "document.md").write_text("gui\n", encoding="utf-8")

    payload = run_gui_cli_parity.compare_artifacts(cli_output, gui_output, artifact_names=("document.md",))

    assert payload["passed"] is False
    assert payload["summary"]["mismatched_count"] == 1
    assert payload["artifacts"][0]["artifact"] == "document.md"
    assert payload["artifacts"][0]["status"] == "mismatched"


def test_release_gate_runner_supports_optional_gui_parity_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote gui_cli_parity_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui-parity",
            gates=["gui-parity"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 1
    assert payload["gates"][0]["gate"] == "gui-parity"
    command = calls[0]
    assert any(str(part).endswith("run_gui_cli_parity.py") for part in command)
    assert "--output-dir" in command
    assert payload["gates"][0]["report_path"].endswith("gui_cli_parity_report.json")


def test_gui_cli_benchmark_policy_is_advisory_by_default() -> None:
    payload = benchmark_gui_cli_parity.apply_benchmark_policy(
        cli_elapsed_ms=100,
        gui_elapsed_ms=150,
        max_gui_duration_ratio=1.2,
        fail_on_regression=False,
    )

    assert payload["passed"] is True
    assert payload["threshold_status"] == "advisory"
    assert payload["gui_duration_ratio"] == 1.5
    assert payload["regressions"][0]["severity"] == "advisory"


def test_gui_cli_benchmark_policy_can_fail_on_threshold() -> None:
    payload = benchmark_gui_cli_parity.apply_benchmark_policy(
        cli_elapsed_ms=100,
        gui_elapsed_ms=150,
        max_gui_duration_ratio=1.2,
        fail_on_regression=True,
    )

    assert payload["passed"] is False
    assert payload["threshold_status"] == "failed"
    assert payload["regressions"][0]["severity"] == "failed"


def test_release_gate_runner_supports_optional_gui_benchmark_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote gui_cli_benchmark_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui-benchmark",
            gates=["gui-benchmark"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 1
    assert payload["gates"][0]["gate"] == "gui-benchmark"
    command = calls[0]
    assert any(str(part).endswith("benchmark_gui_cli_parity.py") for part in command)
    assert "--output-dir" in command
    assert payload["gates"][0]["report_path"].endswith("gui_cli_benchmark_report.json")


def test_wheel_contract_inspector_accepts_gui_resource_and_entry_points(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "pdf2md-0.1.0-py3-none-any.whl"
    _write_wheel(
        wheel_path,
        {
            *inspect_wheel_contract.REQUIRED_WHEEL_MEMBERS,
            "pdf2md-0.1.0.dist-info/entry_points.txt",
        },
        entry_points="\n".join(
            [
                "[console_scripts]",
                "pdf2md = pdf2md.cli:main",
                "pdf2md-gui = pdf2md.gui:main",
                "",
            ]
        ),
    )

    payload = inspect_wheel_contract.inspect_wheel_contract(dist_dir)

    assert payload["status"] == "passed"
    assert payload["summary"]["failed_count"] == 0
    assert any(check["name"] == "wheel_member:pdf2md/resources/GUI_USER_GUIDE.md" for check in payload["checks"])
    assert any(check["name"] == "console_script:pdf2md-gui" for check in payload["checks"])


def test_wheel_contract_inspector_fails_without_gui_help_resource(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "pdf2md-0.1.0-py3-none-any.whl"
    members = set(inspect_wheel_contract.REQUIRED_WHEEL_MEMBERS)
    members.remove("pdf2md/resources/GUI_USER_GUIDE.md")
    members.add("pdf2md-0.1.0.dist-info/entry_points.txt")
    _write_wheel(
        wheel_path,
        members,
        entry_points="\n".join(
            [
                "[console_scripts]",
                "pdf2md = pdf2md.cli:main",
                "pdf2md-gui = pdf2md.gui:main",
                "",
            ]
        ),
    )

    payload = inspect_wheel_contract.inspect_wheel_contract(dist_dir)

    assert payload["status"] == "failed"
    failed = [check for check in payload["checks"] if check["status"] == "failed"]
    assert failed == [
        {
            "name": "wheel_member:pdf2md/resources/GUI_USER_GUIDE.md",
            "status": "failed",
            "message": "missing",
        }
    ]


def _write_wheel(wheel_path: Path, members: set[str], *, entry_points: str) -> None:
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        for member in sorted(members):
            wheel.writestr(member, entry_points if member.endswith("entry_points.txt") else "")
