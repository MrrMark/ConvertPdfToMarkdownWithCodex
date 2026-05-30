from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdf2md.config import Config
from pdf2md import gui_help
from pdf2md.gui import gui_user_guide_path
from pdf2md.gui_runner import (
    GuiDiagnosticError,
    GuiConversionSummary,
    GuiConversionOptions,
    GuiConversionRequest,
    GuiDocumentSummary,
    GuiPageProgress,
    build_batch_config,
    build_single_config,
    check_gui_runtime,
    format_gui_diagnostic_report,
    format_gui_summary,
    gui_diagnostic_report_to_dict,
    gui_options_fingerprint,
    run_gui_conversion,
    validate_gui_request,
)
from pdf2md.models import (
    ConversionStatus,
    DomainAdapterMode,
    ImageMode,
    RagTableOutputMode,
    TableMode,
    WarningEntry,
)
from pdf2md.pipeline import ConversionResult, run_conversion
from tests.fixtures.pdf_builder import build_multi_page_text_pdf
from helpers.normalize_outputs import normalize_manifest, normalize_report


def _batch_file_suffixes(files: dict) -> dict[str, str | None]:
    suffixes: dict[str, str | None] = {}
    for key, value in files.items():
        if value is None:
            suffixes[key] = None
            continue
        path = Path(value)
        parts = path.parts[-2:] if len(path.parts) >= 2 else path.parts
        suffixes[key] = "/".join(parts)
    return suffixes


def _batch_report_contract(payload: dict) -> dict:
    return {
        "schema_version": payload["schema_version"],
        "summary": payload["summary"],
        "documents": [
            {
                "input_pdf": Path(document["input_pdf"]).name,
                "status": document["status"],
                "exit_code": document["exit_code"],
                "warning_count": document["warning_count"],
                "table_count": document["table_count"],
                "image_count": document["image_count"],
                "used_ocr": document["used_ocr"],
                "skipped": document["skipped"],
                "files": _batch_file_suffixes(document["files"]),
            }
            for document in payload["documents"]
        ],
    }


def _corpus_manifest_contract(payload: dict) -> dict:
    return {
        "schema_version": payload["schema_version"],
        "purpose": payload["purpose"],
        "documents": [
            {
                "doc_id": document["doc_id"],
                "input_pdf": Path(document["input_pdf"]).name,
                "source_sha256": document["source_sha256"],
                "status": document["status"],
                "selected_pages": document["selected_pages"],
                "skipped": document["skipped"],
                "files": _batch_file_suffixes(document["files"]),
            }
            for document in payload["documents"]
        ],
    }


def test_gui_module_help_does_not_launch_window() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pdf2md.gui", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "minimal desktop GUI wrapper" in completed.stdout


def test_gui_user_guide_path_points_to_local_help_document() -> None:
    guide_path = gui_user_guide_path()

    assert guide_path.name == "GUI_USER_GUIDE.md"
    assert guide_path.exists()
    assert "GUI 사용자 가이드" in guide_path.read_text(encoding="utf-8")


def test_gui_user_guide_path_falls_back_to_packaged_resource(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(gui_help, "source_gui_user_guide_path", lambda: tmp_path / "missing.md")

    guide_path = gui_help.gui_user_guide_path()

    assert guide_path.name == "GUI_USER_GUIDE.md"
    assert guide_path.exists()
    assert "packaged fallback" in guide_path.read_text(encoding="utf-8")


def test_gui_request_builds_single_config_from_cli_options(sample_pdf: Path, tmp_path: Path) -> None:
    request = GuiConversionRequest(
        input_mode="file",
        input_path=sample_pdf,
        output_dir=tmp_path / "gui-out",
        options=GuiConversionOptions(
            pages="1",
            password="secret",
            image_mode=ImageMode.PLACEHOLDER.value,
            table_mode=TableMode.HTML.value,
            rag_table_output=RagTableOutputMode.BOTH.value,
            rag_profile="technical_spec_rag",
            domain_adapter=DomainAdapterMode.NVME.value,
            confidential_safe_mode=True,
            force_ocr=True,
            ocr_lang="kor+eng",
            keep_page_markers=True,
            remove_header_footer=True,
            dedupe_images=True,
            repair_hyphenation=True,
            figure_crop_fallback=True,
            page_workers=3,
            debug=True,
            verbose=True,
            skip_existing=True,
        ),
    )

    config = build_single_config(request)

    assert config.input_pdf == sample_pdf
    assert config.output_dir == tmp_path / "gui-out"
    assert config.pages == "1"
    assert config.password == "secret"
    assert config.image_mode == ImageMode.PLACEHOLDER.value
    assert config.table_mode == TableMode.HTML.value
    assert config.rag_table_output == RagTableOutputMode.BOTH.value
    assert config.rag_profile == "technical_spec_rag"
    assert config.domain_adapter == DomainAdapterMode.NVME.value
    assert config.confidential_safe_mode is True
    assert config.force_ocr is True
    assert config.ocr_lang == "kor+eng"
    assert config.keep_page_markers is True
    assert config.remove_header_footer is True
    assert config.dedupe_images is True
    assert config.repair_hyphenation is True
    assert config.figure_crop_fallback is True
    assert config.page_workers == 3
    assert config.debug is True
    assert config.verbose is True
    assert config.skip_existing is True


def test_gui_batch_config_preserves_cli_option_contract(sample_pdf: Path, tmp_path: Path) -> None:
    request = GuiConversionRequest(
        input_mode="folder",
        input_path=tmp_path,
        output_dir=tmp_path / "batch-output",
        options=GuiConversionOptions(
            pages="2-3",
            password="secret",
            image_mode=ImageMode.EMBEDDED.value,
            table_mode=TableMode.GFM_ONLY.value,
            rag_table_output=RagTableOutputMode.JSONL.value,
            rag_profile="technical_spec_rag",
            domain_adapter=DomainAdapterMode.TCG.value,
            confidential_safe_mode=True,
            force_ocr=True,
            ocr_lang="kor+eng",
            keep_page_markers=True,
            remove_header_footer=True,
            dedupe_images=True,
            repair_hyphenation=True,
            figure_crop_fallback=True,
            page_workers=4,
            debug=True,
            verbose=True,
            skip_existing=True,
        ),
    )

    config = build_batch_config(request, sample_pdf, tmp_path / "batch-output")

    assert config.pages == "2-3"
    assert config.password == "secret"
    assert config.image_mode == ImageMode.EMBEDDED.value
    assert config.table_mode == TableMode.GFM_ONLY.value
    assert config.rag_table_output == RagTableOutputMode.JSONL.value
    assert config.rag_profile == "technical_spec_rag"
    assert config.domain_adapter == DomainAdapterMode.TCG.value
    assert config.confidential_safe_mode is True
    assert config.force_ocr is True
    assert config.ocr_lang == "kor+eng"
    assert config.keep_page_markers is True
    assert config.remove_header_footer is True
    assert config.dedupe_images is True
    assert config.repair_hyphenation is True
    assert config.figure_crop_fallback is True
    assert config.page_workers == 4
    assert config.debug is True
    assert config.verbose is True
    assert config.skip_existing is True
    assert config.markdown_filename == f"{sample_pdf.stem}.md"
    assert config.manifest_filename == f"{sample_pdf.stem}_manifest.json"
    assert config.report_filename == f"{sample_pdf.stem}_report.json"


def test_gui_runtime_diagnostics_detects_missing_tkinter() -> None:
    def fake_import(name: str) -> object:
        if name == "tkinter":
            raise ModuleNotFoundError("No module named 'tkinter'")
        return object()

    report = check_gui_runtime(
        python_version=(3, 11, 0),
        import_module=fake_import,
        entry_point_names=(),
    )

    assert report.has_errors is True
    assert [diagnostic.code for diagnostic in report.errors] == ["tkinter_unavailable"]
    assert "Tkinter is not available" in report.user_message()


def test_gui_runtime_diagnostics_flags_unsupported_python() -> None:
    report = check_gui_runtime(
        python_version=(3, 10, 9),
        import_module=lambda name: object(),
        entry_point_names=(),
    )

    assert report.has_errors is True
    assert report.errors[0].code == "python_version_unsupported"
    assert "Python 3.11 or newer" in report.user_message()


def test_gui_runtime_missing_entry_point_is_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pdf2md.gui_runner._console_script_names", lambda: set())
    report = check_gui_runtime(
        python_version=(3, 11, 0),
        import_module=lambda name: object(),
        entry_point_names=("pdf2md-gui",),
    )

    assert report.has_errors is False
    assert [diagnostic.code for diagnostic in report.warnings] == ["entry_point_missing"]
    assert "python -m pdf2md.gui" in report.user_message()


def test_gui_runtime_doctor_reports_patchlevel_window_backends_and_help(tmp_path: Path) -> None:
    help_path = tmp_path / "GUI_USER_GUIDE.md"
    help_path.write_text("# help", encoding="utf-8")
    tesseract_path = tmp_path / "tesseract"

    class FakeTcl:
        def eval(self, expression: str) -> str:
            assert expression == "info patchlevel"
            return "8.6.14"

    class FakeRoot:
        def __init__(self) -> None:
            self.destroyed = False

        def withdraw(self) -> None:
            pass

        def update_idletasks(self) -> None:
            pass

        def destroy(self) -> None:
            self.destroyed = True

    tkinter_module = SimpleNamespace(Tcl=FakeTcl, Tk=FakeRoot)

    def fake_import(name: str) -> object:
        if name == "tkinter":
            return tkinter_module
        if name in {"pdf2md.gui", "PIL", "pypdfium2", "pytesseract"}:
            return object()
        raise ModuleNotFoundError(name)

    report = check_gui_runtime(
        python_version=(3, 11, 2),
        import_module=fake_import,
        entry_point_names=(),
        check_window=True,
        help_path=help_path,
        discover_tesseract=lambda: tesseract_path,
        platform_name="Linux",
        environ={"DISPLAY": ":99"},
    )

    codes = {diagnostic.code for diagnostic in report.diagnostics}
    assert report.has_errors is False
    assert {
        "tcl_tk_patchlevel_available",
        "display_environment_present",
        "tk_window_available",
        "pillow_available",
        "pypdfium2_available",
        "pytesseract_available",
        "tesseract_available",
        "help_document_available",
    }.issubset(codes)
    assert all(diagnostic.action for diagnostic in report.diagnostics)
    payload = gui_diagnostic_report_to_dict(report)
    assert payload["kind"] == "gui_runtime_doctor"
    assert payload["passed"] is True
    assert payload["diagnostics"][0]["action"]
    assert "GUI runtime doctor" in format_gui_diagnostic_report(report)


def test_gui_runtime_doctor_missing_optional_backends_are_nonfatal(tmp_path: Path) -> None:
    help_path = tmp_path / "GUI_USER_GUIDE.md"
    help_path.write_text("# help", encoding="utf-8")
    tkinter_module = SimpleNamespace(Tcl=lambda: SimpleNamespace(eval=lambda expression: "8.6.13"))

    def fake_import(name: str) -> object:
        if name == "tkinter":
            return tkinter_module
        if name == "pdf2md.gui":
            return object()
        if name in {"PIL", "pypdfium2", "pytesseract"}:
            raise ModuleNotFoundError(name)
        return object()

    report = check_gui_runtime(
        python_version=(3, 11, 0),
        import_module=fake_import,
        entry_point_names=(),
        check_window=True,
        help_path=help_path,
        discover_tesseract=lambda: None,
        platform_name="Linux",
        environ={},
    )

    severity_by_code = {diagnostic.code: diagnostic.severity for diagnostic in report.diagnostics}
    assert report.has_errors is False
    assert severity_by_code["display_environment_missing"] == "advisory"
    assert severity_by_code["tk_window_check_advisory"] == "advisory"
    assert severity_by_code["pillow_unavailable"] == "warning"
    assert severity_by_code["pypdfium2_unavailable"] == "warning"
    assert severity_by_code["pytesseract_unavailable"] == "advisory"
    assert severity_by_code["tesseract_unavailable"] == "advisory"


def test_gui_runtime_doctor_missing_help_path_is_actionable_warning(tmp_path: Path) -> None:
    missing_help = tmp_path / "missing" / "GUI_USER_GUIDE.md"
    report = check_gui_runtime(
        python_version=(3, 11, 0),
        import_module=lambda name: object(),
        entry_point_names=(),
        help_path=missing_help,
        discover_tesseract=lambda: None,
    )

    help_diagnostic = next(diagnostic for diagnostic in report.diagnostics if diagnostic.code == "help_document_missing")
    assert help_diagnostic.severity == "warning"
    assert help_diagnostic.path == missing_help
    assert "Restore docs/GUI_USER_GUIDE.md" in str(help_diagnostic.action)


def test_gui_runtime_doctor_window_unavailable_is_advisory(tmp_path: Path) -> None:
    help_path = tmp_path / "GUI_USER_GUIDE.md"
    help_path.write_text("# help", encoding="utf-8")

    def unavailable_tk() -> object:
        raise RuntimeError("no display")

    tkinter_module = SimpleNamespace(Tcl=lambda: SimpleNamespace(eval=lambda expression: "8.6.13"), Tk=unavailable_tk)

    def fake_import(name: str) -> object:
        if name == "tkinter":
            return tkinter_module
        if name in {"pdf2md.gui", "PIL", "pypdfium2", "pytesseract"}:
            return object()
        return object()

    report = check_gui_runtime(
        python_version=(3, 11, 0),
        import_module=fake_import,
        entry_point_names=(),
        check_window=True,
        help_path=help_path,
        discover_tesseract=lambda: None,
        platform_name="Linux",
        environ={"DISPLAY": ":99"},
    )

    window_diagnostic = next(diagnostic for diagnostic in report.diagnostics if diagnostic.code == "tk_window_unavailable")
    assert window_diagnostic.severity == "advisory"
    assert report.has_errors is False


def test_gui_request_diagnostics_reject_output_file(sample_pdf: Path, tmp_path: Path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("already a file", encoding="utf-8")
    request = GuiConversionRequest(
        input_mode="file",
        input_path=sample_pdf,
        output_dir=output_file,
    )

    report = validate_gui_request(request)

    assert report.has_errors is True
    assert [diagnostic.code for diagnostic in report.errors] == ["output_not_directory"]
    with pytest.raises(GuiDiagnosticError) as exc_info:
        run_gui_conversion(request)
    assert "Output path exists but is not a directory" in str(exc_info.value)


def test_gui_request_diagnostics_reject_duplicate_batch_stems(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    monkeypatch.setattr(
        "pdf2md.gui_runner.iter_pdf_paths",
        lambda path: [path / "Spec.pdf", path / "spec.PDF"],
    )

    report = validate_gui_request(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=tmp_path / "batch-output",
        )
    )

    assert report.has_errors is True
    assert [diagnostic.code for diagnostic in report.errors] == ["duplicate_pdf_stems"]


def test_gui_request_diagnostics_require_folder_manifest_pair(sample_pdf: Path, tmp_path: Path) -> None:
    manifest_path = tmp_path / "corpus_manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    (input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())

    file_report = validate_gui_request(
        GuiConversionRequest(
            input_mode="file",
            input_path=sample_pdf,
            output_dir=tmp_path / "single-output",
            previous_corpus_manifest=manifest_path,
        )
    )
    reuse_report = validate_gui_request(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=tmp_path / "batch-output",
            reuse_unchanged=True,
        )
    )

    assert file_report.has_errors is True
    assert [diagnostic.code for diagnostic in file_report.errors] == ["incremental_corpus_requires_folder"]
    assert reuse_report.has_errors is True
    assert [diagnostic.code for diagnostic in reuse_report.errors] == ["reuse_unchanged_requires_manifest"]


def test_gui_request_diagnostics_reject_missing_previous_manifest(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    (input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())

    report = validate_gui_request(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=tmp_path / "batch-output",
            previous_corpus_manifest=tmp_path / "missing_corpus_manifest.json",
        )
    )

    assert report.has_errors is True
    assert [diagnostic.code for diagnostic in report.errors] == ["previous_corpus_manifest_missing"]


def test_gui_single_conversion_uses_same_core_output_as_run_conversion(sample_pdf: Path, tmp_path: Path) -> None:
    options = GuiConversionOptions(pages="1", keep_page_markers=True)
    gui_output = tmp_path / "gui-output"
    direct_output = tmp_path / "direct-output"

    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="file",
            input_path=sample_pdf,
            output_dir=gui_output,
            options=options,
        )
    )
    direct_result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=direct_output,
            pages="1",
            keep_page_markers=True,
        )
    )

    assert summary.exit_code == direct_result.exit_code == 0
    assert summary.success_count == 1
    assert summary.document_count == 1
    assert summary.processed_pages == 1
    assert summary.elapsed_ms >= 0
    assert summary.pages_per_second is not None
    assert summary.status_counts["success"] == 1
    assert summary.documents[0].markdown_path == gui_output / "document.md"
    assert summary.documents[0].manifest_path == gui_output / "manifest.json"
    assert summary.documents[0].report_path == gui_output / "report.json"
    assert summary.documents[0].assets_dir == gui_output / "assets"
    assert (gui_output / "document.md").read_text(encoding="utf-8") == (
        direct_output / "document.md"
    ).read_text(encoding="utf-8")
    assert normalize_manifest(json.loads((gui_output / "manifest.json").read_text(encoding="utf-8"))) == (
        normalize_manifest(json.loads((direct_output / "manifest.json").read_text(encoding="utf-8")))
    )
    assert normalize_report(json.loads((gui_output / "report.json").read_text(encoding="utf-8"))) == (
        normalize_report(json.loads((direct_output / "report.json").read_text(encoding="utf-8")))
    )
    text = format_gui_summary(summary)
    assert "documents=1" in text
    assert "processed_pages=1" in text
    assert "pages_per_second=" in text


def test_gui_single_conversion_emits_page_progress_events(tmp_path: Path) -> None:
    pdf_path = tmp_path / "multi.pdf"
    build_multi_page_text_pdf(pdf_path, page_count=3)
    events: list[GuiPageProgress] = []

    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="file",
            input_path=pdf_path,
            output_dir=tmp_path / "gui-output",
        ),
        page_progress=events.append,
    )

    assert summary.exit_code == 0
    assert [(event.current, event.total, event.page, event.percent) for event in events] == [
        (1, 3, 1, 33),
        (2, 3, 2, 67),
        (3, 3, 3, 100),
    ]
    assert all(event.status == "page_finished" for event in events)


def test_gui_batch_conversion_uses_cli_batch_names_and_skip_existing(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    pdf_path = input_dir / "alpha.pdf"
    pdf_path.write_bytes(sample_pdf.read_bytes())
    output_root = tmp_path / "batch-output"
    request = GuiConversionRequest(
        input_mode="folder",
        input_path=input_dir,
        output_dir=output_root,
        options=GuiConversionOptions(pages="1"),
    )

    config = build_batch_config(request, pdf_path, output_root)
    assert config.output_dir == output_root / "alpha"
    assert config.markdown_filename == "alpha.md"
    assert config.manifest_filename == "alpha_manifest.json"
    assert config.report_filename == "alpha_report.json"
    first = run_gui_conversion(request)
    second = run_gui_conversion(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=output_root,
            options=GuiConversionOptions(pages="1", skip_existing=True),
        )
    )

    assert first.success_count == 1
    assert first.batch_report_path == output_root / "batch_report.json"
    assert first.corpus_manifest_path == output_root / "corpus_manifest.json"
    assert (output_root / "batch_report.json").exists()
    assert (output_root / "corpus_manifest.json").exists()
    assert (output_root / "alpha" / "alpha.md").exists()
    assert (output_root / "alpha" / "alpha_manifest.json").exists()
    assert (output_root / "alpha" / "alpha_report.json").exists()
    assert second.skipped_count == 1
    assert second.documents[0].status == "skipped"
    assert second.documents[0].markdown_path == output_root / "alpha" / "alpha.md"
    assert second.documents[0].manifest_path == output_root / "alpha" / "alpha_manifest.json"
    assert second.documents[0].report_path == output_root / "alpha" / "alpha_report.json"
    assert second.documents[0].option_fingerprint == gui_options_fingerprint(
        GuiConversionOptions(pages="1", skip_existing=True)
    )
    batch_report = json.loads((output_root / "batch_report.json").read_text(encoding="utf-8"))
    corpus_manifest = json.loads((output_root / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert batch_report["summary"]["skipped_count"] == 1
    assert batch_report["documents"][0]["status"] == "skipped"
    assert corpus_manifest["documents"][0]["skipped"] is True


def test_gui_batch_artifacts_match_cli_batch_contract(sample_pdf: Path, tmp_path: Path) -> None:
    cli_input_dir = tmp_path / "cli-pdfs"
    gui_input_dir = tmp_path / "gui-pdfs"
    cli_input_dir.mkdir()
    gui_input_dir.mkdir()
    (cli_input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())
    (gui_input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())

    completed = subprocess.run(
        [sys.executable, "-m", "pdf2md", "--input-dir", str(cli_input_dir), "--pages", "1"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0

    gui_output_root = tmp_path / "gui-output"
    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="folder",
            input_path=gui_input_dir,
            output_dir=gui_output_root,
            options=GuiConversionOptions(pages="1"),
        )
    )

    assert summary.exit_code == 0
    assert summary.batch_report_path == gui_output_root / "batch_report.json"
    assert summary.corpus_manifest_path == gui_output_root / "corpus_manifest.json"
    cli_report = json.loads((cli_input_dir / "output" / "batch_report.json").read_text(encoding="utf-8"))
    gui_report = json.loads((gui_output_root / "batch_report.json").read_text(encoding="utf-8"))
    cli_manifest = json.loads((cli_input_dir / "output" / "corpus_manifest.json").read_text(encoding="utf-8"))
    gui_manifest = json.loads((gui_output_root / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert _batch_report_contract(gui_report) == _batch_report_contract(cli_report)
    assert _corpus_manifest_contract(gui_manifest) == _corpus_manifest_contract(cli_manifest)


def test_gui_incremental_batch_matches_cli_reuse_contract(sample_pdf: Path, tmp_path: Path) -> None:
    previous_input_dir = tmp_path / "previous-pdfs"
    cli_current_input_dir = tmp_path / "cli-current-pdfs"
    gui_current_input_dir = tmp_path / "gui-current-pdfs"
    previous_input_dir.mkdir()
    cli_current_input_dir.mkdir()
    gui_current_input_dir.mkdir()
    for folder in (previous_input_dir, cli_current_input_dir, gui_current_input_dir):
        (folder / "alpha.pdf").write_bytes(sample_pdf.read_bytes())

    previous_run = subprocess.run(
        [sys.executable, "-m", "pdf2md", "--input-dir", str(previous_input_dir), "--pages", "1"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert previous_run.returncode == 0
    previous_manifest = previous_input_dir / "output" / "corpus_manifest.json"

    cli_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf2md",
            "--input-dir",
            str(cli_current_input_dir),
            "--pages",
            "1",
            "--previous-corpus-manifest",
            str(previous_manifest),
            "--reuse-unchanged",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cli_run.returncode == 0

    gui_output_root = tmp_path / "gui-output"
    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="folder",
            input_path=gui_current_input_dir,
            output_dir=gui_output_root,
            previous_corpus_manifest=previous_manifest,
            reuse_unchanged=True,
            options=GuiConversionOptions(pages="1"),
        )
    )

    assert summary.exit_code == 0
    assert summary.skipped_count == 1
    assert summary.corpus_diff_report_path == gui_output_root / "corpus_diff_report.json"
    assert summary.requirement_change_impact_report_path == gui_output_root / "requirement_change_impact_report.json"
    assert (gui_output_root / "alpha" / "alpha.md").exists()
    assert "corpus_diff=" in format_gui_summary(summary)
    assert "requirement_impact=" in format_gui_summary(summary)
    cli_output_root = cli_current_input_dir / "output"
    cli_batch = json.loads((cli_output_root / "batch_report.json").read_text(encoding="utf-8"))
    gui_batch = json.loads((gui_output_root / "batch_report.json").read_text(encoding="utf-8"))
    assert cli_batch["summary"]["skipped_count"] == gui_batch["summary"]["skipped_count"] == 1
    cli_diff = json.loads((cli_output_root / "corpus_diff_report.json").read_text(encoding="utf-8"))
    gui_diff = json.loads((gui_output_root / "corpus_diff_report.json").read_text(encoding="utf-8"))
    assert cli_diff["summary"] == gui_diff["summary"] == {
        "added_count": 0,
        "changed_count": 0,
        "removed_count": 0,
        "unchanged_count": 1,
    }
    cli_impact = json.loads((cli_output_root / "requirement_change_impact_report.json").read_text(encoding="utf-8"))
    gui_impact = json.loads((gui_output_root / "requirement_change_impact_report.json").read_text(encoding="utf-8"))
    assert cli_impact["summary"] == gui_impact["summary"]


def test_gui_batch_uses_deterministic_case_stable_order(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    for name in ("Beta.pdf", "alpha.pdf", "gamma.pdf"):
        (input_dir / name).write_bytes(sample_pdf.read_bytes())

    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=tmp_path / "batch-output",
            options=GuiConversionOptions(pages="1"),
        )
    )

    assert [document.input_pdf.name for document in summary.documents] == ["alpha.pdf", "Beta.pdf", "gamma.pdf"]


def test_gui_batch_cancel_marks_remaining_documents(monkeypatch: pytest.MonkeyPatch, sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    for name in ("alpha.pdf", "beta.pdf"):
        (input_dir / name).write_bytes(sample_pdf.read_bytes())
    completed: list[str] = []
    progress_events: list[tuple[int, int, str, str]] = []

    def fake_run_conversion(config) -> ConversionResult:  # noqa: ANN001
        completed.append(config.input_pdf.name)
        return ConversionResult(
            exit_code=0,
            markdown_path=config.output_dir / config.markdown_filename,
            manifest_path=config.output_dir / config.manifest_filename,
            report_path=config.output_dir / config.report_filename,
            warnings=[],
            status=ConversionStatus.SUCCESS,
        )

    monkeypatch.setattr("pdf2md.gui_runner.run_conversion", fake_run_conversion)
    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=tmp_path / "batch-output",
            options=GuiConversionOptions(pages="1"),
        ),
        batch_progress=lambda event: progress_events.append(
            (event.current, event.total, event.input_pdf.name, event.status)
        ),
        cancel_requested=lambda: bool(completed),
    )

    assert completed == ["alpha.pdf"]
    assert summary.success_count == 1
    assert summary.cancelled_count == 1
    assert summary.exit_code == 2
    assert [document.status for document in summary.documents] == ["success", "cancelled"]
    assert progress_events[-1] == (2, 2, "beta.pdf", "cancelled")


def test_gui_batch_failure_becomes_retry_candidate(monkeypatch: pytest.MonkeyPatch, sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    for name in ("alpha.pdf", "beta.pdf"):
        (input_dir / name).write_bytes(sample_pdf.read_bytes())

    def fake_run_conversion(config) -> ConversionResult:  # noqa: ANN001
        if config.input_pdf.name == "beta.pdf":
            raise RuntimeError("backend failed")
        return ConversionResult(
            exit_code=0,
            markdown_path=config.output_dir / config.markdown_filename,
            manifest_path=config.output_dir / config.manifest_filename,
            report_path=config.output_dir / config.report_filename,
            warnings=[],
            status=ConversionStatus.SUCCESS,
        )

    monkeypatch.setattr("pdf2md.gui_runner.run_conversion", fake_run_conversion)
    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=tmp_path / "batch-output",
            options=GuiConversionOptions(pages="1"),
        )
    )

    assert summary.success_count == 1
    assert summary.failed_count == 1
    assert summary.exit_code == 2
    assert (tmp_path / "batch-output" / "batch_report.json").exists()
    batch_report = json.loads((tmp_path / "batch-output" / "batch_report.json").read_text(encoding="utf-8"))
    assert batch_report["summary"]["failed_count"] == 1
    assert len(summary.retry_candidates) == 1
    retry = summary.retry_candidates[0]
    assert retry.input_pdf.name == "beta.pdf"
    assert retry.retry_candidate is True
    assert retry.option_fingerprint == gui_options_fingerprint(GuiConversionOptions(pages="1"))
    assert "retry_candidates=1" in format_gui_summary(summary)


def test_gui_option_fingerprint_is_deterministic_and_option_sensitive() -> None:
    baseline = gui_options_fingerprint(GuiConversionOptions(pages="1", skip_existing=True))
    same = gui_options_fingerprint(GuiConversionOptions(pages="1", skip_existing=True))
    changed = gui_options_fingerprint(GuiConversionOptions(pages="2", skip_existing=True))

    assert baseline == same
    assert baseline != changed
    assert len(baseline) == 16


def test_gui_summary_uses_structured_warning_counts(monkeypatch: pytest.MonkeyPatch, sample_pdf: Path, tmp_path: Path) -> None:
    def fake_run_conversion(config) -> ConversionResult:  # noqa: ANN001
        return ConversionResult(
            exit_code=2,
            markdown_path=config.output_dir / config.markdown_filename,
            manifest_path=config.output_dir / config.manifest_filename,
            report_path=config.output_dir / config.report_filename,
            warnings=[
                WarningEntry(code="TABLE_FALLBACK", message="table fallback", page=2),
                WarningEntry(code="OCR_LOW_CONFIDENCE", message="low confidence", page=1),
                WarningEntry(code="TABLE_FALLBACK", message="table fallback duplicate", page=3),
            ],
            status=ConversionStatus.PARTIAL_SUCCESS,
        )

    monkeypatch.setattr("pdf2md.gui_runner.run_conversion", fake_run_conversion)
    output_dir = tmp_path / "partial-output"
    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="file",
            input_path=sample_pdf,
            output_dir=output_dir,
        )
    )
    document = summary.documents[0]

    assert summary.partial_success_count == 1
    assert document.warning_count == 3
    assert document.warning_codes == ("OCR_LOW_CONFIDENCE", "TABLE_FALLBACK")
    text = format_gui_summary(summary)
    assert "warnings=3 (OCR_LOW_CONFIDENCE, TABLE_FALLBACK)" in text
    assert "table fallback duplicate" not in text


def test_gui_summary_separates_actionable_and_advisory_warning_counts(tmp_path: Path) -> None:
    summary = GuiConversionSummary(
        input_mode="file",
        input_path=tmp_path / "input.pdf",
        output_root=tmp_path / "out",
        documents=[
            GuiDocumentSummary(
                input_pdf=tmp_path / "input.pdf",
                output_dir=tmp_path / "out",
                status="success",
                exit_code=0,
                warning_count=3,
                actionable_warning_count=1,
                advisory_warning_count=2,
                warning_codes=("OCR_EMPTY_RESULT", "TABLE_COMPLEXITY_HTML_FALLBACK"),
            )
        ],
        exit_code=0,
    )

    text = format_gui_summary(summary)

    assert "warnings=3 (actionable=1, advisory=2; OCR_EMPTY_RESULT, TABLE_COMPLEXITY_HTML_FALLBACK)" in text
