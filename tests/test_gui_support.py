from __future__ import annotations

import json
from pathlib import Path

from pdf2md.gui_runner import (
    GUI_STATUS_CANCELLED,
    GuiConversionSummary,
    GuiDiagnostic,
    GuiDiagnosticReport,
    GuiDocumentSummary,
)
from pdf2md.gui_support import (
    build_gui_support_bundle,
    render_support_bundle_markdown,
    sanitize_support_path_label,
    support_bundle_redaction_findings,
    write_gui_support_bundle,
)


def test_gui_support_bundle_sanitizes_summary_paths_and_warning_messages(tmp_path: Path) -> None:
    input_pdf = tmp_path / "sensitive customer" / "secret.pdf"
    output_root = tmp_path / "out"
    output_root.mkdir(parents=True)
    markdown = output_root / "document.md"
    manifest = output_root / "manifest.json"
    report = output_root / "report.json"
    markdown.write_text("raw source text must not be copied", encoding="utf-8")
    manifest.write_text("{}", encoding="utf-8")
    report.write_text('{"warnings":[{"message":"table fallback secret"}]}', encoding="utf-8")
    summary = GuiConversionSummary(
        input_mode="file",
        input_path=input_pdf,
        output_root=output_root,
        documents=[
            GuiDocumentSummary(
                input_pdf=input_pdf,
                output_dir=output_root,
                status="partial_success",
                exit_code=2,
                markdown_path=markdown,
                manifest_path=manifest,
                report_path=report,
                assets_dir=output_root / "assets",
                warning_count=2,
                warning_codes=("OCR_LOW_CONFIDENCE", "TABLE_FALLBACK"),
                retry_candidate=False,
                message="table fallback secret",
            )
        ],
        exit_code=2,
    )

    bundle = build_gui_support_bundle(summary=summary, roots=(tmp_path,))
    serialized = json.dumps(bundle, ensure_ascii=False, sort_keys=True)

    assert bundle["conversion_summary"]["status_counts"]["partial_success"] == 1
    assert bundle["conversion_summary"]["warning_count"] == 2
    assert bundle["conversion_summary"]["warning_codes"] == ["OCR_LOW_CONFIDENCE", "TABLE_FALLBACK"]
    assert str(tmp_path) not in serialized
    assert "table fallback secret" not in serialized
    assert "raw source text" not in serialized
    assert bundle["conversion_summary"]["documents"][0]["artifacts"]["markdown"]["label"].startswith("<root-1>/")
    assert support_bundle_redaction_findings(bundle, forbidden_values=("table fallback secret",), roots=(tmp_path,)) == []


def test_gui_support_bundle_failure_fixture_keeps_only_counts_codes_and_retry(tmp_path: Path) -> None:
    input_dir = tmp_path / "private inputs"
    output_root = tmp_path / "support-output"
    summary = GuiConversionSummary(
        input_mode="folder",
        input_path=input_dir,
        output_root=output_root,
        documents=[
            GuiDocumentSummary(
                input_pdf=input_dir / "partial-secret.pdf",
                output_dir=output_root / "partial-secret",
                status="partial_success",
                exit_code=2,
                warning_count=3,
                warning_codes=("OCR_LOW_CONFIDENCE", "TABLE_FALLBACK"),
                retry_candidate=False,
                message=f"warning message leaked {tmp_path}/partial-secret.pdf",
            ),
            GuiDocumentSummary(
                input_pdf=input_dir / "failed-secret.pdf",
                output_dir=output_root / "failed-secret",
                status="failed",
                exit_code=1,
                warning_count=1,
                warning_codes=("GUI_CONVERSION_FAILED",),
                retry_candidate=True,
                message=f"Traceback raw exception at {tmp_path}/failed-secret.pdf",
            ),
        ],
        exit_code=2,
    )

    bundle = build_gui_support_bundle(summary=summary, roots=(tmp_path,))
    serialized = json.dumps(bundle, ensure_ascii=False, sort_keys=True)
    documents = bundle["conversion_summary"]["documents"]

    assert bundle["conversion_summary"]["status_counts"]["partial_success"] == 1
    assert bundle["conversion_summary"]["status_counts"]["failed"] == 1
    assert bundle["conversion_summary"]["warning_count"] == 4
    assert bundle["conversion_summary"]["warning_codes"] == [
        "GUI_CONVERSION_FAILED",
        "OCR_LOW_CONFIDENCE",
        "TABLE_FALLBACK",
    ]
    assert documents[1]["retry_candidate"] is True
    assert documents[1]["warning_codes"] == ["GUI_CONVERSION_FAILED"]
    assert "Traceback raw exception" not in serialized
    assert "warning message leaked" not in serialized
    assert str(tmp_path) not in serialized
    assert support_bundle_redaction_findings(
        bundle,
        forbidden_values=("Traceback raw exception", "warning message leaked"),
        roots=(tmp_path,),
    ) == []


def test_gui_support_bundle_keeps_runtime_codes_without_messages_or_paths(tmp_path: Path) -> None:
    runtime_report = GuiDiagnosticReport(
        [
            GuiDiagnostic(
                code="tk_window_unavailable",
                severity="advisory",
                message=f"display failed at {tmp_path}",
                path=tmp_path / "secret",
                action=f"open {tmp_path}",
            ),
            GuiDiagnostic(
                code="help_document_missing",
                severity="warning",
                message="missing docs/GUI_USER_GUIDE.md",
                action="restore help",
            ),
        ]
    )

    bundle = build_gui_support_bundle(runtime_report=runtime_report, roots=(tmp_path,))
    serialized = json.dumps(bundle, ensure_ascii=False, sort_keys=True)

    assert bundle["runtime"]["advisory_count"] == 1
    assert bundle["runtime"]["warning_count"] == 1
    assert bundle["runtime"]["diagnostics"] == [
        {"code": "tk_window_unavailable", "severity": "advisory"},
        {"code": "help_document_missing", "severity": "warning"},
    ]
    assert str(tmp_path) not in serialized
    assert "display failed" not in serialized
    assert "restore help" not in serialized


def test_gui_support_bundle_summarizes_smoke_evidence_without_raw_payload(tmp_path: Path) -> None:
    smoke_evidence = {
        "status": "failed",
        "summary": {
            "failed_check_count": 1,
            "failed_checks": [
                {
                    "code": "single_preserve_failed",
                    "next_action": f"inspect {tmp_path}/private.pdf",
                }
            ],
        },
        "runtime": {
            "diagnostics": [
                {
                    "code": "python_version_supported",
                    "severity": "info",
                    "message": f"runtime path {tmp_path}",
                    "action": "No action required.",
                }
            ]
        },
        "runner_smoke": [
            {
                "name": "single_preserve",
                "passed": False,
                "input_mode": "file",
                "error": "raw PDF text must not appear",
                "status_counts": {"failed": 1},
            }
        ],
    }

    bundle = build_gui_support_bundle(smoke_evidence=smoke_evidence, roots=(tmp_path,))
    serialized = json.dumps(bundle, ensure_ascii=False, sort_keys=True)

    assert bundle["smoke_evidence"]["status"] == "failed"
    assert bundle["smoke_evidence"]["failed_check_codes"] == ["single_preserve_failed"]
    assert bundle["smoke_evidence"]["runtime_codes"] == ["python_version_supported"]
    assert "raw PDF text" not in serialized
    assert "private.pdf" not in serialized
    assert str(tmp_path) not in serialized


def test_gui_support_bundle_writer_outputs_stable_json_and_markdown(tmp_path: Path) -> None:
    bundle = build_gui_support_bundle(
        summary=GuiConversionSummary(
            input_mode="folder",
            input_path=tmp_path / "pdfs",
            output_root=tmp_path / "out",
            documents=[
                GuiDocumentSummary(
                    input_pdf=tmp_path / "pdfs" / "cancelled.pdf",
                    output_dir=tmp_path / "out" / "cancelled",
                    status=GUI_STATUS_CANCELLED,
                    exit_code=2,
                    warning_count=0,
                    warning_codes=(),
                )
            ],
            exit_code=2,
        ),
        roots=(tmp_path,),
    )

    json_path, markdown_path = write_gui_support_bundle(bundle, tmp_path / "support")
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert loaded["schema_version"] == "1.0"
    assert loaded["redaction_policy"]["stores_absolute_paths"] is False
    assert "# GUI Support Bundle" in markdown
    assert "status_counts" not in markdown
    assert str(tmp_path) not in json.dumps(loaded, ensure_ascii=False)
    assert str(tmp_path) not in markdown
    assert render_support_bundle_markdown(bundle).endswith("\n")


def test_sanitize_support_path_label_never_returns_absolute_path(tmp_path: Path) -> None:
    label = sanitize_support_path_label(tmp_path / "out" / "document.md", roots=(tmp_path,))

    assert label == "<root-1>/out/document.md"
    assert str(tmp_path) not in label
