from __future__ import annotations

import importlib
from importlib import metadata as importlib_metadata
import hashlib
import inspect
import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from pdf2md.batch_runner import (
    BatchConversionOptions,
    BatchDocumentEvent,
    BatchDocumentResult,
    BatchRunResult,
    build_batch_config as build_shared_batch_config,
    detect_duplicate_stems,
    iter_pdf_paths,
    run_batch_conversion as run_shared_batch_conversion,
)
from pdf2md.config import Config, default_output_dir_for_input
from pdf2md.gui_help import gui_user_guide_path
from pdf2md.models import (
    ConversionStatus,
    DomainAdapterMode,
    ImageMode,
    OutputProfile,
    RagSidecarScope,
    RagTableOutputMode,
    Report,
    TableMode,
    WarningEntry,
)
from pdf2md.pipeline import EXIT_FATAL, EXIT_PARTIAL, ConversionProgressEvent, ConversionResult, run_conversion
from pdf2md.rag_profiles import DEFAULT_RAG_PURPOSE_PROFILE, normalize_rag_profile


ProgressCallback = Callable[[str], None]
BatchProgressCallback = Callable[["GuiBatchProgress"], None]
PageProgressCallback = Callable[["GuiPageProgress"], None]
CancelCallback = Callable[[], bool]
DiagnosticSeverity = Literal["info", "advisory", "warning", "error"]
MIN_GUI_PYTHON_VERSION = (3, 11)
GUI_STATUS_SKIPPED = "skipped"
GUI_STATUS_CANCELLED = "cancelled"


@dataclass(frozen=True)
class GuiDiagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    path: Path | None = None
    action: str | None = None


@dataclass(frozen=True)
class GuiDiagnosticReport:
    diagnostics: list[GuiDiagnostic]

    @property
    def errors(self) -> list[GuiDiagnostic]:
        return [diagnostic for diagnostic in self.diagnostics if diagnostic.severity == "error"]

    @property
    def warnings(self) -> list[GuiDiagnostic]:
        return [diagnostic for diagnostic in self.diagnostics if diagnostic.severity == "warning"]

    @property
    def advisories(self) -> list[GuiDiagnostic]:
        return [diagnostic for diagnostic in self.diagnostics if diagnostic.severity == "advisory"]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def user_message(self) -> str:
        lines = []
        for diagnostic in self.errors or self.warnings:
            path_text = f" ({diagnostic.path})" if diagnostic.path is not None else ""
            action_text = f" Action: {diagnostic.action}" if diagnostic.action else ""
            lines.append(f"- {diagnostic.message}{path_text}{action_text}")
        return "\n".join(lines)


class GuiDiagnosticError(RuntimeError):
    def __init__(self, report: GuiDiagnosticReport) -> None:
        self.report = report
        super().__init__(report.user_message() or "GUI diagnostics failed.")


@dataclass(frozen=True)
class GuiConversionOptions:
    pages: str | None = None
    password: str | None = None
    image_mode: str = ImageMode.REFERENCED.value
    table_mode: str = TableMode.AUTO.value
    rag_table_output: str = RagTableOutputMode.NONE.value
    output_profile: str = OutputProfile.FULL.value
    rag_sidecar_scope: str | None = None
    rag_profile: str = DEFAULT_RAG_PURPOSE_PROFILE
    domain_adapter: str = DomainAdapterMode.NONE.value
    confidential_safe_mode: bool = False
    force_ocr: bool = False
    ocr_lang: str = "eng"
    keep_page_markers: bool = False
    remove_header_footer: bool = False
    dedupe_images: bool = False
    repair_hyphenation: bool = False
    figure_crop_fallback: bool = False
    retrieval_chunk_max_tokens: int = 512
    retrieval_tokenizer: str = "char"
    rag_contextual_embedding_text: bool = False
    rag_merge_sibling_text_chunks: bool = False
    rag_chunk_relationship_metadata: bool = False
    rag_figure_text_chunks: bool = False
    page_workers: int = 1
    debug: bool = False
    verbose: bool = False
    skip_existing: bool = False


@dataclass(frozen=True)
class GuiConversionRequest:
    input_mode: str
    input_path: Path
    output_dir: Path | None = None
    previous_corpus_manifest: Path | None = None
    reuse_unchanged: bool = False
    options: GuiConversionOptions = field(default_factory=GuiConversionOptions)


@dataclass(frozen=True)
class GuiBatchProgress:
    current: int
    total: int
    input_pdf: Path
    status: str


@dataclass(frozen=True)
class GuiPageProgress:
    current: int
    total: int
    page: int
    percent: int
    stage: str
    status: str


@dataclass(frozen=True)
class GuiReportMetrics:
    warning_codes: tuple[str, ...] = ()
    processed_pages: int = 0
    pages_per_second: float | None = None


@dataclass(frozen=True)
class GuiDocumentSummary:
    input_pdf: Path
    output_dir: Path
    status: str
    exit_code: int
    markdown_path: Path | None = None
    manifest_path: Path | None = None
    report_path: Path | None = None
    assets_dir: Path | None = None
    warning_count: int = 0
    actionable_warning_count: int = 0
    advisory_warning_count: int = 0
    warning_codes: tuple[str, ...] = ()
    duration_ms: int = 0
    processed_pages: int = 0
    pages_per_second: float | None = None
    skipped: bool = False
    retry_candidate: bool = False
    option_fingerprint: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class GuiConversionSummary:
    input_mode: str
    input_path: Path
    output_root: Path
    documents: list[GuiDocumentSummary]
    exit_code: int
    batch_report_path: Path | None = None
    corpus_manifest_path: Path | None = None
    corpus_diff_report_path: Path | None = None
    requirement_change_impact_report_path: Path | None = None

    @property
    def success_count(self) -> int:
        return sum(1 for document in self.documents if document.status == ConversionStatus.SUCCESS.value)

    @property
    def partial_success_count(self) -> int:
        return sum(1 for document in self.documents if document.status == ConversionStatus.PARTIAL_SUCCESS.value)

    @property
    def failed_count(self) -> int:
        return sum(1 for document in self.documents if document.status == ConversionStatus.FAILED.value)

    @property
    def skipped_count(self) -> int:
        return sum(1 for document in self.documents if document.skipped)

    @property
    def cancelled_count(self) -> int:
        return sum(1 for document in self.documents if document.status == GUI_STATUS_CANCELLED)

    @property
    def retry_candidates(self) -> tuple[GuiDocumentSummary, ...]:
        return tuple(document for document in self.documents if document.retry_candidate)

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def elapsed_ms(self) -> int:
        return sum(document.duration_ms for document in self.documents)

    @property
    def processed_pages(self) -> int:
        return sum(document.processed_pages for document in self.documents)

    @property
    def pages_per_second(self) -> float | None:
        if self.document_count == 1:
            return self.documents[0].pages_per_second
        if self.elapsed_ms <= 0 or self.processed_pages <= 0:
            return None
        return round(self.processed_pages / (self.elapsed_ms / 1000), 4)

    @property
    def status_counts(self) -> dict[str, int]:
        return {
            "success": self.success_count,
            "partial_success": self.partial_success_count,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "cancelled": self.cancelled_count,
        }


def warning_codes_for_display(warnings: list[WarningEntry]) -> tuple[str, ...]:
    """Return deterministic warning codes for GUI display without copying source text."""
    return tuple(sorted({warning.code for warning in warnings}))


def format_gui_summary(summary: GuiConversionSummary) -> str:
    """Format a compact GUI result summary using artifact paths and structured warning counts."""
    pages_per_second = _format_rate(summary.pages_per_second)
    lines = [
        (
            "Finished: "
            f"documents={summary.document_count}, "
            f"success={summary.success_count}, "
            f"partial={summary.partial_success_count}, "
            f"failed={summary.failed_count}, "
            f"skipped={summary.skipped_count}, "
            f"cancelled={summary.cancelled_count}, "
            f"retry_candidates={len(summary.retry_candidates)}, "
            f"elapsed_ms={summary.elapsed_ms}, "
            f"processed_pages={summary.processed_pages}, "
            f"pages_per_second={pages_per_second}, "
            f"output={summary.output_root}"
        )
    ]
    for document in summary.documents:
        warning_text = f", warnings={document.warning_count}" if document.warning_count else ""
        warning_parts: list[str] = []
        if document.actionable_warning_count or document.advisory_warning_count:
            warning_parts.append(
                f"actionable={document.actionable_warning_count}, advisory={document.advisory_warning_count}"
            )
        if document.warning_codes:
            warning_parts.append(", ".join(document.warning_codes))
        if warning_parts:
            warning_text += f" ({'; '.join(warning_parts)})"
        retry_text = ", retry_candidate=true" if document.retry_candidate else ""
        lines.append(
            f"- {document.input_pdf.name}: status={document.status}{warning_text}, "
            f"markdown={document.markdown_path}, report={document.report_path}, manifest={document.manifest_path}"
            f"{retry_text}"
        )
    if summary.batch_report_path is not None:
        lines.append(f"- batch_report={summary.batch_report_path}")
    if summary.corpus_manifest_path is not None:
        lines.append(f"- corpus_manifest={summary.corpus_manifest_path}")
    if summary.corpus_diff_report_path is not None:
        lines.append(f"- corpus_diff={summary.corpus_diff_report_path}")
    if summary.requirement_change_impact_report_path is not None:
        lines.append(f"- requirement_impact={summary.requirement_change_impact_report_path}")
    return "\n".join(lines)


def _format_rate(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _format_version(version: Sequence[int]) -> str:
    parts = list(version[:3])
    if len(parts) < 3:
        parts.extend([0] * (3 - len(parts)))
    return ".".join(str(part) for part in parts)


def _console_script_names() -> set[str]:
    entry_points = importlib_metadata.entry_points()
    if hasattr(entry_points, "select"):
        return {entry_point.name for entry_point in entry_points.select(group="console_scripts")}
    return {entry_point.name for entry_point in entry_points.get("console_scripts", [])}


def _default_gui_help_path() -> Path:
    return gui_user_guide_path()


def _discover_tesseract() -> Path | None:
    executable = shutil.which("tesseract")
    if executable:
        return Path(executable)
    homebrew_tesseract = Path("/opt/homebrew/bin/tesseract")
    if homebrew_tesseract.exists():
        return homebrew_tesseract
    return None


def _tk_patchlevel_diagnostic(tkinter_module: object) -> GuiDiagnostic | None:
    tcl_factory = getattr(tkinter_module, "Tcl", None)
    if not callable(tcl_factory):
        return None
    try:
        patchlevel = str(tcl_factory().eval("info patchlevel"))
    except Exception as exc:  # noqa: BLE001
        return GuiDiagnostic(
            code="tcl_tk_patchlevel_unavailable",
            severity="warning",
            message=f"Tcl/Tk patchlevel could not be inspected. Details: {exc}",
            action="Verify the Python installation includes a working Tcl/Tk runtime.",
        )
    return GuiDiagnostic(
        code="tcl_tk_patchlevel_available",
        severity="info",
        message=f"Tcl/Tk patchlevel is available: {patchlevel}.",
        action="No action required.",
    )


def _display_environment_diagnostic(
    *,
    platform_name: str,
    environ: Mapping[str, str],
) -> tuple[GuiDiagnostic, bool]:
    if platform_name == "Linux":
        if environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY"):
            return (
                GuiDiagnostic(
                    code="display_environment_present",
                    severity="info",
                    message="Linux display environment variables are present.",
                    action="No action required.",
                ),
                False,
            )
        return (
            GuiDiagnostic(
                code="display_environment_missing",
                severity="advisory",
                message="No Linux DISPLAY or WAYLAND_DISPLAY value was found; Tk window launch is likely unavailable.",
                action="Run the GUI from a desktop session, or keep using CLI/headless smoke checks in CI.",
            ),
            True,
        )
    if platform_name in {"Darwin", "Windows"}:
        return (
            GuiDiagnostic(
                code="display_environment_platform_default",
                severity="info",
                message=f"{platform_name} desktop display availability is checked by the optional Tk window probe.",
                action="Run the doctor from the same desktop session used to launch the GUI.",
            ),
            False,
        )
    return (
        GuiDiagnostic(
            code="display_environment_unknown",
            severity="advisory",
            message=f"Display environment checks are not specialized for platform: {platform_name or 'unknown'}.",
            action="Run the GUI doctor locally and confirm the Tk window can open on this platform.",
        ),
        False,
    )


def _tk_window_diagnostic(
    *,
    tkinter_module: object,
) -> GuiDiagnostic:
    tk_factory = getattr(tkinter_module, "Tk", None)
    if not callable(tk_factory):
        return GuiDiagnostic(
            code="tk_window_probe_unavailable",
            severity="advisory",
            message="Tkinter is importable, but no Tk window factory was found for a window availability probe.",
            action="Run python -m pdf2md.gui from a desktop session to confirm launch behavior.",
        )
    root = None
    try:
        root = tk_factory()
        if hasattr(root, "withdraw"):
            root.withdraw()
        if hasattr(root, "update_idletasks"):
            root.update_idletasks()
    except Exception as exc:  # noqa: BLE001
        return GuiDiagnostic(
            code="tk_window_unavailable",
            severity="advisory",
            message=f"Tkinter imported, but a Tk window could not be created. Details: {exc}",
            action="Use a desktop session with display access, or keep GUI window checks out of CI.",
        )
    finally:
        if root is not None and hasattr(root, "destroy"):
            try:
                root.destroy()
            except Exception:  # noqa: BLE001
                pass
    return GuiDiagnostic(
        code="tk_window_available",
        severity="info",
        message="Tkinter can create and destroy a window in this session.",
        action="No action required.",
    )


def _optional_module_diagnostic(
    *,
    module_name: str,
    display_name: str,
    success_code: str,
    missing_code: str,
    importer: Callable[[str], object],
    missing_severity: DiagnosticSeverity,
    missing_action: str,
) -> GuiDiagnostic:
    try:
        importer(module_name)
    except Exception as exc:  # noqa: BLE001
        return GuiDiagnostic(
            code=missing_code,
            severity=missing_severity,
            message=f"{display_name} is not importable. Details: {exc}",
            action=missing_action,
        )
    return GuiDiagnostic(
        code=success_code,
        severity="info",
        message=f"{display_name} is importable.",
        action="No action required.",
    )


def _package_distribution_diagnostic() -> GuiDiagnostic:
    try:
        distribution = importlib_metadata.distribution("pdf2md")
    except Exception as exc:  # noqa: BLE001
        return GuiDiagnostic(
            code="package_distribution_missing",
            severity="advisory",
            message=f"Installed package metadata for pdf2md was not found. Details: {exc}",
            action="This is expected in some source checkout runs; use pip install -e .[dev] for editable packaging smoke.",
        )
    mode = "installed"
    direct_url = distribution.read_text("direct_url.json")
    if direct_url and '"editable": true' in direct_url:
        mode = "editable"
    location = Path(str(distribution.locate_file("")))
    return GuiDiagnostic(
        code="package_distribution_available",
        severity="info",
        message=f"pdf2md package metadata is available: version={distribution.version}, mode={mode}.",
        path=location,
        action="Compare this mode with the intended source checkout, editable install, or wheel smoke path.",
    )


def check_gui_runtime(
    *,
    python_version: Sequence[int] | None = None,
    import_module: Callable[[str], object] | None = None,
    entry_point_names: Sequence[str] = ("pdf2md-gui",),
    check_window: bool = False,
    help_path: Path | None = None,
    discover_tesseract: Callable[[], Path | None] | None = None,
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> GuiDiagnosticReport:
    """Check GUI runtime prerequisites, optionally probing Tk window creation."""
    version = python_version or sys.version_info
    importer = import_module or importlib.import_module
    display_platform = platform_name if platform_name is not None else platform.system()
    display_environ = environ if environ is not None else os.environ
    tesseract_discovery = discover_tesseract or _discover_tesseract
    resolved_help_path = help_path if help_path is not None else _default_gui_help_path()
    diagnostics: list[GuiDiagnostic] = []
    if tuple(version[:2]) < MIN_GUI_PYTHON_VERSION:
        diagnostics.append(
            GuiDiagnostic(
                code="python_version_unsupported",
                severity="error",
                message=(
                    "Python 3.11 or newer is required for the supported GUI path; "
                    f"current interpreter is {_format_version(version)}."
                ),
                action="Install Python 3.11 or newer and recreate the virtual environment.",
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="python_version_supported",
                severity="info",
                message=f"Python runtime is supported: {_format_version(version)}.",
                action="No action required.",
            )
        )

    tkinter_module: object | None = None
    try:
        tkinter_module = importer("tkinter")
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(
            GuiDiagnostic(
                code="tkinter_unavailable",
                severity="error",
                message=(
                    "Tkinter is not available. Install a Python build with Tcl/Tk support "
                    f"before launching the GUI. Details: {exc}"
                ),
                action="Install a Python distribution that includes Tcl/Tk, then rerun the GUI doctor.",
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="tkinter_available",
                severity="info",
                message="Tkinter runtime is available.",
                action="No action required.",
            )
        )
        patchlevel_diagnostic = _tk_patchlevel_diagnostic(tkinter_module)
        if patchlevel_diagnostic is not None:
            diagnostics.append(patchlevel_diagnostic)

    display_diagnostic, skip_window_probe = _display_environment_diagnostic(
        platform_name=display_platform,
        environ=display_environ,
    )
    diagnostics.append(display_diagnostic)
    if tkinter_module is not None:
        if check_window and not skip_window_probe:
            diagnostics.append(_tk_window_diagnostic(tkinter_module=tkinter_module))
        else:
            diagnostics.append(
                GuiDiagnostic(
                    code="tk_window_check_advisory",
                    severity="advisory",
                    message="Tk window creation was not attempted during this headless-safe runtime check.",
                    action=(
                        "Run python -m pdf2md.gui --doctor --doctor-check-window "
                        "from a desktop session for an optional window probe."
                    ),
                )
            )

    try:
        importer("pdf2md.gui")
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(
            GuiDiagnostic(
                code="gui_module_unavailable",
                severity="error",
                message=f"The pdf2md.gui module cannot be imported. Reinstall the package. Details: {exc}",
                action="Reinstall the package from the source checkout or wheel and rerun python -m pdf2md.gui --help.",
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="gui_module_available",
                severity="info",
                message="pdf2md.gui module is importable.",
                action="No action required.",
            )
        )

    diagnostics.append(_package_distribution_diagnostic())

    diagnostics.append(
        _optional_module_diagnostic(
            module_name="PIL",
            display_name="Pillow",
            success_code="pillow_available",
            missing_code="pillow_unavailable",
            importer=importer,
            missing_severity="warning",
            missing_action="Install project dependencies with pip install -e .[dev] or from the wheel metadata.",
        )
    )
    diagnostics.append(
        _optional_module_diagnostic(
            module_name="pypdfium2",
            display_name="pypdfium2",
            success_code="pypdfium2_available",
            missing_code="pypdfium2_unavailable",
            importer=importer,
            missing_severity="warning",
            missing_action="Install pypdfium2 before using OCR page rendering paths.",
        )
    )
    diagnostics.append(
        _optional_module_diagnostic(
            module_name="pytesseract",
            display_name="pytesseract",
            success_code="pytesseract_available",
            missing_code="pytesseract_unavailable",
            importer=importer,
            missing_severity="advisory",
            missing_action="Install pytesseract if OCR will be used from the GUI.",
        )
    )
    tesseract_path = tesseract_discovery()
    if tesseract_path is None:
        diagnostics.append(
            GuiDiagnostic(
                code="tesseract_unavailable",
                severity="advisory",
                message="The tesseract executable was not found on PATH.",
                action="Install Tesseract and language data before using OCR options.",
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="tesseract_available",
                severity="info",
                message="The tesseract executable is available.",
                path=tesseract_path,
                action="Run tesseract --list-langs if OCR language data needs to be verified.",
            )
        )

    if resolved_help_path.exists():
        diagnostics.append(
            GuiDiagnostic(
                code="help_document_available",
                severity="info",
                message="The local GUI help document is available.",
                path=resolved_help_path,
                action="No action required.",
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="help_document_missing",
                severity="warning",
                message="The local GUI help document was not found.",
                path=resolved_help_path,
                action="Restore docs/GUI_USER_GUIDE.md or reinstall from a complete source/wheel package.",
            )
        )

    if entry_point_names:
        try:
            installed_scripts = _console_script_names()
        except Exception as exc:  # noqa: BLE001
            diagnostics.append(
                GuiDiagnostic(
                    code="entry_point_check_failed",
                    severity="warning",
                    message=(
                        "Could not inspect installed console scripts. "
                        f"`python -m pdf2md.gui` remains available. Details: {exc}"
                    ),
                    action="Use python -m pdf2md.gui, or reinstall the package if console scripts are required.",
                )
            )
        else:
            for script_name in entry_point_names:
                if script_name in installed_scripts:
                    diagnostics.append(
                        GuiDiagnostic(
                            code="entry_point_available",
                            severity="info",
                            message=f"Console script is installed: {script_name}.",
                            action="No action required.",
                        )
                    )
                else:
                    diagnostics.append(
                        GuiDiagnostic(
                            code="entry_point_missing",
                            severity="warning",
                            message=(
                                f"Console script `{script_name}` is not installed in this environment. "
                                "Run `python -m pdf2md.gui` or install the package with `pip install -e .`."
                            ),
                            action="Install the package in editable or wheel mode if the console script is required.",
                        )
                    )
    return GuiDiagnosticReport(diagnostics)


def gui_diagnostic_report_to_dict(report: GuiDiagnosticReport) -> dict[str, Any]:
    """Return a deterministic local-only dictionary for GUI runtime diagnostics."""
    return {
        "kind": "gui_runtime_doctor",
        "passed": not report.has_errors,
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "advisory_count": len(report.advisories),
        "diagnostics": [
            {
                "code": diagnostic.code,
                "severity": diagnostic.severity,
                "message": diagnostic.message,
                "action": diagnostic.action,
                "path": str(diagnostic.path) if diagnostic.path is not None else None,
            }
            for diagnostic in report.diagnostics
        ],
    }


def format_gui_diagnostic_report(report: GuiDiagnosticReport) -> str:
    """Render GUI runtime doctor diagnostics for local terminal use."""
    payload = gui_diagnostic_report_to_dict(report)
    lines = [
        "GUI runtime doctor",
        (
            f"- Status: {'passed' if payload['passed'] else 'failed'} "
            f"(errors={payload['error_count']}, warnings={payload['warning_count']}, "
            f"advisories={payload['advisory_count']})"
        ),
    ]
    for diagnostic in report.diagnostics:
        lines.append(f"- [{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}")
        if diagnostic.path is not None:
            lines.append(f"  Path: {diagnostic.path}")
        if diagnostic.action:
            lines.append(f"  Action: {diagnostic.action}")
    return "\n".join(lines)


def _path_is_readable(path: Path) -> bool:
    mode = os.R_OK | (os.X_OK if path.is_dir() else 0)
    return os.access(path, mode)


def _path_is_writable_directory(path: Path) -> bool:
    return os.access(path, os.W_OK | os.X_OK)


def _nearest_existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _validate_output_dir(output_dir: Path, diagnostics: list[GuiDiagnostic]) -> None:
    if output_dir.exists():
        if not output_dir.is_dir():
            diagnostics.append(
                GuiDiagnostic(
                    code="output_not_directory",
                    severity="error",
                    message="Output path exists but is not a directory.",
                    path=output_dir,
                )
            )
        elif not _path_is_writable_directory(output_dir):
            diagnostics.append(
                GuiDiagnostic(
                    code="output_not_writable",
                    severity="error",
                    message="Output directory is not writable.",
                    path=output_dir,
                )
            )
        return

    ancestor = _nearest_existing_ancestor(output_dir.parent)
    if not ancestor.exists():
        diagnostics.append(
            GuiDiagnostic(
                code="output_parent_missing",
                severity="error",
                message="No existing parent directory was found for the output path.",
                path=output_dir,
            )
        )
    elif not ancestor.is_dir():
        diagnostics.append(
            GuiDiagnostic(
                code="output_parent_not_directory",
                severity="error",
                message="The nearest existing output parent is not a directory.",
                path=ancestor,
            )
        )
    elif not _path_is_writable_directory(ancestor):
        diagnostics.append(
            GuiDiagnostic(
                code="output_parent_not_writable",
                severity="error",
                message="The nearest existing output parent is not writable.",
                path=ancestor,
            )
        )


def validate_gui_request(request: GuiConversionRequest) -> GuiDiagnosticReport:
    """Validate GUI input/output paths before invoking the conversion pipeline."""
    diagnostics: list[GuiDiagnostic] = []
    mode = request.input_mode.lower()
    input_path = request.input_path

    if mode == "file":
        if not input_path.exists() or not input_path.is_file():
            diagnostics.append(
                GuiDiagnostic(
                    code="input_file_missing",
                    severity="error",
                    message="Input PDF does not exist or is not a file.",
                    path=input_path,
                )
            )
        elif input_path.suffix.lower() != ".pdf":
            diagnostics.append(
                GuiDiagnostic(
                    code="input_not_pdf",
                    severity="error",
                    message="Input file must use the .pdf extension.",
                    path=input_path,
                )
            )
        elif not _path_is_readable(input_path):
            diagnostics.append(
                GuiDiagnostic(
                    code="input_not_readable",
                    severity="error",
                    message="Input PDF is not readable.",
                    path=input_path,
                )
            )
        output_dir = request.output_dir if request.output_dir is not None else default_output_dir_for_input(input_path)
        _validate_output_dir(output_dir, diagnostics)
        if request.previous_corpus_manifest is not None or request.reuse_unchanged:
            diagnostics.append(
                GuiDiagnostic(
                    code="incremental_corpus_requires_folder",
                    severity="error",
                    message="Incremental corpus options are only supported for PDF folder input.",
                    action="Switch input mode to PDF folder before selecting a previous corpus manifest.",
                )
            )
    elif mode == "folder":
        if not input_path.exists() or not input_path.is_dir():
            diagnostics.append(
                GuiDiagnostic(
                    code="input_folder_missing",
                    severity="error",
                    message="Input folder does not exist or is not a directory.",
                    path=input_path,
                )
            )
        elif not _path_is_readable(input_path):
            diagnostics.append(
                GuiDiagnostic(
                    code="input_folder_not_readable",
                    severity="error",
                    message="Input folder is not readable.",
                    path=input_path,
                )
            )
        else:
            pdf_paths = iter_pdf_paths(input_path)
            if not pdf_paths:
                diagnostics.append(
                    GuiDiagnostic(
                        code="input_folder_empty",
                        severity="error",
                        message="Input folder does not contain direct child PDF files.",
                        path=input_path,
                    )
                )
            duplicates = detect_duplicate_stems(pdf_paths)
            if duplicates:
                diagnostics.append(
                    GuiDiagnostic(
                        code="duplicate_pdf_stems",
                        severity="error",
                        message=f"Duplicate PDF stems would produce conflicting batch outputs: {'; '.join(duplicates)}.",
                        path=input_path,
                    )
                )
        output_root = request.output_dir if request.output_dir is not None else input_path / "output"
        _validate_output_dir(output_root, diagnostics)
        if request.reuse_unchanged and request.previous_corpus_manifest is None:
            diagnostics.append(
                GuiDiagnostic(
                    code="reuse_unchanged_requires_manifest",
                    severity="error",
                    message="Reuse unchanged requires a previous corpus manifest.",
                    action="Select a previous corpus_manifest.json or turn off reuse unchanged.",
                )
            )
        if request.previous_corpus_manifest is not None:
            _validate_previous_corpus_manifest(request.previous_corpus_manifest, diagnostics)
    else:
        if request.previous_corpus_manifest is not None or request.reuse_unchanged:
            diagnostics.append(
                GuiDiagnostic(
                    code="incremental_corpus_requires_folder",
                    severity="error",
                    message="Incremental corpus options are only supported for PDF folder input.",
                    action="Switch input mode to PDF folder before selecting a previous corpus manifest.",
                )
            )
        diagnostics.append(
            GuiDiagnostic(
                code="input_mode_unsupported",
                severity="error",
                message=f"Unsupported GUI input mode: {request.input_mode}.",
            )
        )
    return GuiDiagnosticReport(diagnostics)


def _validate_previous_corpus_manifest(path: Path, diagnostics: list[GuiDiagnostic]) -> None:
    if not path.exists() or not path.is_file():
        diagnostics.append(
            GuiDiagnostic(
                code="previous_corpus_manifest_missing",
                severity="error",
                message="Previous corpus manifest does not exist or is not a file.",
                path=path,
                action="Select an existing corpus_manifest.json file.",
            )
        )
    elif path.suffix.lower() != ".json":
        diagnostics.append(
            GuiDiagnostic(
                code="previous_corpus_manifest_not_json",
                severity="error",
                message="Previous corpus manifest must be a JSON file.",
                path=path,
                action="Select the previous batch output corpus_manifest.json file.",
            )
        )


def _coerce_options(options: GuiConversionOptions) -> dict:
    return {
        "pages": options.pages or None,
        "password": options.password or None,
        "image_mode": ImageMode(options.image_mode),
        "table_mode": TableMode(options.table_mode),
        "rag_table_output": RagTableOutputMode(options.rag_table_output),
        "output_profile": OutputProfile(options.output_profile),
        "rag_sidecar_scope": RagSidecarScope(options.rag_sidecar_scope) if options.rag_sidecar_scope is not None else None,
        "rag_profile": normalize_rag_profile(options.rag_profile),
        "domain_adapter": DomainAdapterMode(options.domain_adapter),
        "confidential_safe_mode": options.confidential_safe_mode,
        "force_ocr": options.force_ocr,
        "ocr_lang": options.ocr_lang or "eng",
        "keep_page_markers": options.keep_page_markers,
        "remove_header_footer": options.remove_header_footer,
        "dedupe_images": options.dedupe_images,
        "repair_hyphenation": options.repair_hyphenation,
        "figure_crop_fallback": options.figure_crop_fallback,
        "retrieval_chunk_max_tokens": options.retrieval_chunk_max_tokens,
        "retrieval_tokenizer": options.retrieval_tokenizer,
        "rag_contextual_embedding_text": options.rag_contextual_embedding_text,
        "rag_merge_sibling_text_chunks": options.rag_merge_sibling_text_chunks,
        "rag_chunk_relationship_metadata": options.rag_chunk_relationship_metadata,
        "rag_figure_text_chunks": options.rag_figure_text_chunks,
        "page_workers": options.page_workers,
        "debug": options.debug,
        "verbose": options.verbose,
        "skip_existing": options.skip_existing,
    }


def _batch_options_from_gui(options: GuiConversionOptions) -> BatchConversionOptions:
    return BatchConversionOptions(
        pages=options.pages or None,
        password=options.password or None,
        image_mode=ImageMode(options.image_mode),
        table_mode=TableMode(options.table_mode),
        rag_table_output=RagTableOutputMode(options.rag_table_output),
        output_profile=OutputProfile(options.output_profile),
        rag_sidecar_scope=RagSidecarScope(options.rag_sidecar_scope) if options.rag_sidecar_scope is not None else None,
        rag_profile=normalize_rag_profile(options.rag_profile),
        domain_adapter=DomainAdapterMode(options.domain_adapter),
        confidential_safe_mode=options.confidential_safe_mode,
        force_ocr=options.force_ocr,
        ocr_lang=options.ocr_lang or "eng",
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
        rag_figure_text_chunks=options.rag_figure_text_chunks,
        page_workers=options.page_workers,
        debug=options.debug,
        verbose=options.verbose,
        skip_existing=options.skip_existing,
    )


def _batch_options_from_request(request: GuiConversionRequest) -> BatchConversionOptions:
    options = _batch_options_from_gui(request.options)
    return BatchConversionOptions(
        pages=options.pages,
        password=options.password,
        image_mode=options.image_mode,
        table_mode=options.table_mode,
        rag_table_output=options.rag_table_output,
        output_profile=options.output_profile,
        rag_sidecar_scope=options.rag_sidecar_scope,
        rag_profile=options.rag_profile,
        domain_adapter=options.domain_adapter,
        confidential_safe_mode=options.confidential_safe_mode,
        force_ocr=options.force_ocr,
        ocr_lang=options.ocr_lang,
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
        rag_figure_text_chunks=options.rag_figure_text_chunks,
        page_workers=options.page_workers,
        debug=options.debug,
        verbose=options.verbose,
        skip_existing=options.skip_existing,
        previous_corpus_manifest=request.previous_corpus_manifest,
        reuse_unchanged=request.reuse_unchanged,
    )


def gui_options_fingerprint(options: GuiConversionOptions) -> str:
    """Return a deterministic local-only fingerprint for GUI conversion options."""
    payload = json.dumps(asdict(options), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_single_config(request: GuiConversionRequest) -> Config:
    """Build the same single-document Config used by the CLI path."""
    input_pdf = request.input_path
    output_dir = request.output_dir if request.output_dir is not None else default_output_dir_for_input(input_pdf)
    return Config(input_pdf=input_pdf, output_dir=output_dir, **_coerce_options(request.options))


def build_batch_config(request: GuiConversionRequest, pdf_path: Path, output_root: Path) -> Config:
    """Build a batch-document Config using the CLI batch naming contract."""
    return build_shared_batch_config(pdf_path, output_root, _batch_options_from_gui(request.options))


def _has_existing_core_outputs(config: Config) -> bool:
    return all(
        (config.output_dir / filename).exists()
        for filename in (config.markdown_filename, config.manifest_filename, config.report_filename)
    )


def _markdown_path(config: Config) -> Path:
    return config.output_dir / config.markdown_filename


def _manifest_path(config: Config) -> Path:
    return config.output_dir / config.manifest_filename


def _report_path(config: Config) -> Path:
    return config.output_dir / config.report_filename


def _assets_dir(config: Config) -> Path:
    return config.output_dir / config.assets_dirname


def _document_summary_from_result(
    config: Config,
    result: ConversionResult,
    *,
    option_fingerprint: str | None = None,
) -> GuiDocumentSummary:
    report = result.report
    return GuiDocumentSummary(
        input_pdf=config.input_pdf,
        output_dir=config.output_dir,
        status=result.status.value,
        exit_code=result.exit_code,
        markdown_path=result.markdown_path or _markdown_path(config),
        manifest_path=result.manifest_path or _manifest_path(config),
        report_path=result.report_path or _report_path(config),
        assets_dir=_assets_dir(config),
        warning_count=len(result.warnings),
        actionable_warning_count=report.summary.actionable_warning_count if report is not None else 0,
        advisory_warning_count=report.summary.advisory_warning_count if report is not None else 0,
        warning_codes=warning_codes_for_display(result.warnings),
        duration_ms=report.duration_ms if report is not None else 0,
        processed_pages=report.summary.processed_pages if report is not None else 0,
        pages_per_second=report.summary.pages_per_second if report is not None else None,
        retry_candidate=result.status == ConversionStatus.FAILED,
        option_fingerprint=option_fingerprint,
    )


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _emit_batch_progress(
    batch_progress: BatchProgressCallback | None,
    *,
    current: int,
    total: int,
    input_pdf: Path,
    status: str,
) -> None:
    if batch_progress is not None:
        batch_progress(GuiBatchProgress(current=current, total=total, input_pdf=input_pdf, status=status))


def _gui_page_progress_from_event(event: ConversionProgressEvent) -> GuiPageProgress | None:
    if event.status != "page_finished" or event.page is None or event.total <= 0:
        return None
    safe_current = min(max(event.current, 0), event.total)
    return GuiPageProgress(
        current=safe_current,
        total=event.total,
        page=event.page,
        percent=round((safe_current / event.total) * 100),
        stage=event.stage,
        status=event.status,
    )


def _run_core_conversion(
    config: Config,
    *,
    page_progress: PageProgressCallback | None = None,
) -> ConversionResult:
    if page_progress is None:
        return run_conversion(config)

    def handle_progress(event: ConversionProgressEvent) -> None:
        gui_event = _gui_page_progress_from_event(event)
        if gui_event is not None:
            page_progress(gui_event)

    if "progress" not in inspect.signature(run_conversion).parameters:
        return run_conversion(config)
    return run_conversion(config, progress=handle_progress)


def _run_single(
    request: GuiConversionRequest,
    progress: ProgressCallback | None,
    page_progress: PageProgressCallback | None,
) -> GuiConversionSummary:
    config = build_single_config(request)
    _emit(progress, f"Converting {config.input_pdf}")
    result = _run_core_conversion(config, page_progress=page_progress)
    _emit(progress, f"Finished {config.input_pdf.name}: {result.status.value}")
    document = _document_summary_from_result(config, result, option_fingerprint=gui_options_fingerprint(request.options))
    return GuiConversionSummary(
        input_mode="file",
        input_path=request.input_path,
        output_root=config.output_dir,
        documents=[document],
        exit_code=result.exit_code,
    )


def _cancelled_document_summary(config: Config, option_fingerprint: str) -> GuiDocumentSummary:
    return GuiDocumentSummary(
        input_pdf=config.input_pdf,
        output_dir=config.output_dir,
        status=GUI_STATUS_CANCELLED,
        exit_code=EXIT_PARTIAL,
        markdown_path=_markdown_path(config),
        manifest_path=_manifest_path(config),
        report_path=_report_path(config),
        assets_dir=_assets_dir(config),
        option_fingerprint=option_fingerprint,
        message="cancelled before conversion",
    )


def _failed_document_summary(config: Config, exc: Exception, option_fingerprint: str) -> GuiDocumentSummary:
    return GuiDocumentSummary(
        input_pdf=config.input_pdf,
        output_dir=config.output_dir,
        status=ConversionStatus.FAILED.value,
        exit_code=EXIT_FATAL,
        markdown_path=_markdown_path(config),
        manifest_path=_manifest_path(config),
        report_path=_report_path(config),
        assets_dir=_assets_dir(config),
        retry_candidate=True,
        option_fingerprint=option_fingerprint,
        message=str(exc),
    )


def _report_metrics_from_report(config: Config) -> GuiReportMetrics:
    report_path = config.output_dir / config.report_filename
    if not report_path.exists():
        return GuiReportMetrics()
    try:
        report = Report.model_validate(json.loads(report_path.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return GuiReportMetrics()
    return GuiReportMetrics(
        warning_codes=warning_codes_for_display(list(report.warnings)),
        processed_pages=report.summary.processed_pages,
        pages_per_second=report.summary.pages_per_second,
    )


def _document_summary_from_batch_document(
    request: GuiConversionRequest,
    output_root: Path,
    pdf_path: Path,
    document: BatchDocumentResult,
    *,
    option_fingerprint: str,
) -> GuiDocumentSummary:
    config = build_batch_config(request, pdf_path, output_root)
    status = document.status
    report_metrics = _report_metrics_from_report(config)
    return GuiDocumentSummary(
        input_pdf=pdf_path,
        output_dir=config.output_dir,
        status=status,
        exit_code=document.exit_code,
        markdown_path=_markdown_path(config),
        manifest_path=_manifest_path(config),
        report_path=_report_path(config),
        assets_dir=_assets_dir(config),
        warning_count=document.warning_count,
        warning_codes=report_metrics.warning_codes,
        duration_ms=document.duration_ms,
        processed_pages=report_metrics.processed_pages,
        pages_per_second=report_metrics.pages_per_second,
        skipped=document.skipped,
        retry_candidate=status == ConversionStatus.FAILED.value,
        option_fingerprint=option_fingerprint,
        message="cancelled before conversion" if status == GUI_STATUS_CANCELLED else None,
    )


def _handle_batch_event(
    event: BatchDocumentEvent,
    *,
    progress: ProgressCallback | None,
    batch_progress: BatchProgressCallback | None,
) -> None:
    if event.status == "started":
        _emit(progress, f"Converting {event.input_pdf}")
    elif event.status == GUI_STATUS_SKIPPED:
        _emit(progress, f"Skipped {event.input_pdf.name}: existing core outputs")
    elif event.status == GUI_STATUS_CANCELLED:
        _emit(progress, f"Cancelled {event.input_pdf.name}: request received before conversion")
    elif event.status == ConversionStatus.FAILED.value:
        _emit(progress, f"Failed {event.input_pdf.name}: conversion failed")
    else:
        _emit(progress, f"Finished {event.input_pdf.name}: {event.status}")
    _emit_batch_progress(
        batch_progress,
        current=event.current,
        total=event.total,
        input_pdf=event.input_pdf,
        status=event.status,
    )


def _run_batch(
    request: GuiConversionRequest,
    progress: ProgressCallback | None,
    batch_progress: BatchProgressCallback | None,
    cancel_requested: CancelCallback | None,
) -> GuiConversionSummary:
    input_dir = request.input_path
    output_root = request.output_dir if request.output_dir is not None else input_dir / "output"
    option_fingerprint = gui_options_fingerprint(request.options)
    batch_result: BatchRunResult = run_shared_batch_conversion(
        input_dir=input_dir,
        output_root=output_root,
        options=_batch_options_from_request(request),
        run_document=run_conversion,
        progress=lambda event: _handle_batch_event(event, progress=progress, batch_progress=batch_progress),
        cancel_requested=cancel_requested,
        catch_document_exceptions=True,
    )
    documents = [
        _document_summary_from_batch_document(
            request,
            batch_result.output_root,
            pdf_path,
            document,
            option_fingerprint=option_fingerprint,
        )
        for pdf_path, document in zip(batch_result.pdf_paths, batch_result.documents)
    ]
    return GuiConversionSummary(
        input_mode="folder",
        input_path=input_dir,
        output_root=batch_result.output_root,
        documents=documents,
        exit_code=batch_result.exit_code,
        batch_report_path=batch_result.batch_report_path,
        corpus_manifest_path=batch_result.corpus_manifest_path,
        corpus_diff_report_path=batch_result.corpus_diff_report_path,
        requirement_change_impact_report_path=batch_result.requirement_change_impact_report_path,
    )


def run_gui_conversion(
    request: GuiConversionRequest,
    *,
    progress: ProgressCallback | None = None,
    batch_progress: BatchProgressCallback | None = None,
    page_progress: PageProgressCallback | None = None,
    cancel_requested: CancelCallback | None = None,
) -> GuiConversionSummary:
    """Run a GUI-initiated conversion through the same core pipeline as CLI conversions."""
    diagnostics = validate_gui_request(request)
    if diagnostics.has_errors:
        raise GuiDiagnosticError(diagnostics)
    mode = request.input_mode.lower()
    if mode == "file":
        if not request.input_path.exists() or not request.input_path.is_file():
            raise ValueError(f"Input PDF does not exist or is not a file: {request.input_path}")
        if request.input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {request.input_path}")
        return _run_single(request, progress, page_progress)
    if mode == "folder":
        return _run_batch(request, progress, batch_progress, cancel_requested)
    raise ValueError(f"Unsupported GUI input mode: {request.input_mode}")
