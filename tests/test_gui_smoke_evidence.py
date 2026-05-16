from __future__ import annotations

import json
from pathlib import Path

from pdf2md.gui_runner import GuiDiagnostic, GuiDiagnosticReport
from scripts import run_gui_smoke_evidence as smoke


def test_gui_smoke_redaction_removes_local_absolute_roots(tmp_path: Path) -> None:
    text = f"{Path.cwd().resolve()}/docs {Path.home().resolve()}/profile {tmp_path}/smoke"

    redacted = smoke.redact_text(text, roots=(tmp_path,))

    assert str(Path.cwd().resolve()) not in redacted
    assert str(Path.home().resolve()) not in redacted
    assert str(tmp_path) not in redacted
    assert "<workspace>" in redacted or "<redacted-" in redacted


def test_gui_smoke_failure_summary_and_exit_code_contract() -> None:
    evidence = {
        "runtime": {"passed": False},
        "commands": [{"name": "gui_module_help", "passed": False}],
        "state": {"passed": False},
        "runner_smoke": [
            {
                "name": "single_preserve",
                "passed": True,
                "documents": [
                    {
                        "artifacts": {
                            "markdown": {"exists": False},
                            "manifest": {"exists": True},
                            "report": {"exists": True},
                            "assets_dir": {"exists": False},
                        }
                    }
                ],
            }
        ],
    }

    finalized = smoke.finalize_evidence(evidence)

    assert finalized["status"] == "failed"
    assert smoke.exit_code_for_evidence(finalized) == smoke.EXIT_SMOKE_FAILED
    assert [failure["code"] for failure in finalized["summary"]["failed_checks"]] == [
        "gui_runtime_failed",
        "gui_module_help_failed",
        "gui_state_isolation_failed",
        "single_preserve_missing_artifacts",
    ]
    assert all(failure["next_action"] for failure in finalized["summary"]["failed_checks"])


def test_gui_smoke_evidence_stores_only_sanitized_counts_and_labels(
    monkeypatch,  # noqa: ANN001
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        smoke,
        "check_gui_runtime",
        lambda: GuiDiagnosticReport(
            [
                GuiDiagnostic(
                    code="python_version_supported",
                    severity="info",
                    message="Python runtime is supported.",
                    action="No action required.",
                ),
                GuiDiagnostic(
                    code="tkinter_available",
                    severity="info",
                    message="Tkinter runtime is available.",
                    action="No action required.",
                ),
                GuiDiagnostic(
                    code="tk_window_check_advisory",
                    severity="advisory",
                    message="Tk window creation was not attempted.",
                    action="Run python -m pdf2md.gui --doctor from a desktop session.",
                ),
            ]
        ),
    )
    output_dir = tmp_path / "gui-smoke"
    state_path = tmp_path / "state" / "gui_state.json"

    evidence = smoke.run_smoke(output_dir, state_path)
    serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True)

    assert evidence["status"] == "passed"
    assert evidence["runtime"]["kind"] == "gui_runtime_doctor"
    assert evidence["runtime"]["advisory_count"] == 1
    assert all("action" in diagnostic for diagnostic in evidence["runtime"]["diagnostics"])
    assert evidence["summary"]["redaction_findings"] == []
    assert str(tmp_path) not in serialized
    assert smoke.SINGLE_FIXTURE_TEXT not in serialized
    for forbidden in smoke.BATCH_FIXTURE_TEXTS:
        assert forbidden not in serialized
    assert "table fallback" not in serialized.lower()
    assert "warning message" not in serialized.lower()
    assert {record["preset"] for record in evidence["runner_smoke"]} == {
        "preserve",
        "custom",
        "rag_optimized",
    }
    for record in evidence["runner_smoke"]:
        assert record["passed"] is True
        for document in record["documents"]:
            assert document["artifacts"]["markdown"]["exists"] is True
            assert document["artifacts"]["manifest"]["exists"] is True
            assert document["artifacts"]["report"]["exists"] is True
            assert document["warning_codes"] == []


def test_gui_smoke_evidence_writer_uses_stable_json(tmp_path: Path) -> None:
    evidence = smoke.finalize_evidence(
        {
            "runtime": {"passed": True},
            "commands": [{"name": "gui_module_help", "passed": True}],
            "state": {"passed": True},
            "runner_smoke": [],
        }
    )

    evidence_path = smoke.write_evidence(evidence, tmp_path)
    loaded = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert evidence_path.name == smoke.EVIDENCE_FILENAME
    assert loaded["status"] == "passed"
    assert smoke.exit_code_for_evidence(loaded) == 0
