from __future__ import annotations

import importlib
from importlib import metadata as importlib_metadata
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Sequence

from pdf2md.config import Config, default_output_dir_for_input
from pdf2md.models import ConversionStatus, DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode, WarningEntry
from pdf2md.pipeline import EXIT_FATAL, EXIT_PARTIAL, ConversionResult, run_conversion


ProgressCallback = Callable[[str], None]
BatchProgressCallback = Callable[["GuiBatchProgress"], None]
CancelCallback = Callable[[], bool]
DiagnosticSeverity = Literal["info", "warning", "error"]
MIN_GUI_PYTHON_VERSION = (3, 11)
GUI_STATUS_SKIPPED = "skipped"
GUI_STATUS_CANCELLED = "cancelled"


@dataclass(frozen=True)
class GuiDiagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    path: Path | None = None


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
    def has_errors(self) -> bool:
        return bool(self.errors)

    def user_message(self) -> str:
        lines = []
        for diagnostic in self.errors or self.warnings:
            path_text = f" ({diagnostic.path})" if diagnostic.path is not None else ""
            lines.append(f"- {diagnostic.message}{path_text}")
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
    domain_adapter: str = DomainAdapterMode.NONE.value
    confidential_safe_mode: bool = False
    force_ocr: bool = False
    ocr_lang: str = "eng"
    keep_page_markers: bool = False
    remove_header_footer: bool = False
    dedupe_images: bool = False
    repair_hyphenation: bool = False
    figure_crop_fallback: bool = False
    page_workers: int = 1
    debug: bool = False
    verbose: bool = False
    skip_existing: bool = False


@dataclass(frozen=True)
class GuiConversionRequest:
    input_mode: str
    input_path: Path
    output_dir: Path | None = None
    options: GuiConversionOptions = field(default_factory=GuiConversionOptions)


@dataclass(frozen=True)
class GuiBatchProgress:
    current: int
    total: int
    input_pdf: Path
    status: str


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
    warning_codes: tuple[str, ...] = ()
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


def warning_codes_for_display(warnings: list[WarningEntry]) -> tuple[str, ...]:
    """Return deterministic warning codes for GUI display without copying source text."""
    return tuple(sorted({warning.code for warning in warnings}))


def format_gui_summary(summary: GuiConversionSummary) -> str:
    """Format a compact GUI result summary using artifact paths and structured warning counts."""
    lines = [
        (
            "Finished: "
            f"success={summary.success_count}, "
            f"partial={summary.partial_success_count}, "
            f"failed={summary.failed_count}, "
            f"skipped={summary.skipped_count}, "
            f"cancelled={summary.cancelled_count}, "
            f"retry_candidates={len(summary.retry_candidates)}, "
            f"output={summary.output_root}"
        )
    ]
    for document in summary.documents:
        warning_text = f", warnings={document.warning_count}" if document.warning_count else ""
        if document.warning_codes:
            warning_text += f" ({', '.join(document.warning_codes)})"
        retry_text = ", retry_candidate=true" if document.retry_candidate else ""
        lines.append(
            f"- {document.input_pdf.name}: status={document.status}{warning_text}, "
            f"markdown={document.markdown_path}, report={document.report_path}, manifest={document.manifest_path}"
            f"{retry_text}"
        )
    return "\n".join(lines)


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


def check_gui_runtime(
    *,
    python_version: Sequence[int] | None = None,
    import_module: Callable[[str], object] | None = None,
    entry_point_names: Sequence[str] = ("pdf2md-gui",),
) -> GuiDiagnosticReport:
    """Check GUI runtime prerequisites without launching a desktop window."""
    version = python_version or sys.version_info
    importer = import_module or importlib.import_module
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
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="python_version_supported",
                severity="info",
                message=f"Python runtime is supported: {_format_version(version)}.",
            )
        )

    try:
        importer("tkinter")
    except Exception as exc:  # noqa: BLE001
        diagnostics.append(
            GuiDiagnostic(
                code="tkinter_unavailable",
                severity="error",
                message=(
                    "Tkinter is not available. Install a Python build with Tcl/Tk support "
                    f"before launching the GUI. Details: {exc}"
                ),
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="tkinter_available",
                severity="info",
                message="Tkinter runtime is available.",
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
            )
        )
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="gui_module_available",
                severity="info",
                message="pdf2md.gui module is importable.",
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
                        )
                    )
    return GuiDiagnosticReport(diagnostics)


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
            duplicates = _detect_duplicate_stems(pdf_paths)
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
    else:
        diagnostics.append(
            GuiDiagnostic(
                code="input_mode_unsupported",
                severity="error",
                message=f"Unsupported GUI input mode: {request.input_mode}.",
            )
        )
    return GuiDiagnosticReport(diagnostics)


def _coerce_options(options: GuiConversionOptions) -> dict:
    return {
        "pages": options.pages or None,
        "password": options.password or None,
        "image_mode": ImageMode(options.image_mode),
        "table_mode": TableMode(options.table_mode),
        "rag_table_output": RagTableOutputMode(options.rag_table_output),
        "domain_adapter": DomainAdapterMode(options.domain_adapter),
        "confidential_safe_mode": options.confidential_safe_mode,
        "force_ocr": options.force_ocr,
        "ocr_lang": options.ocr_lang or "eng",
        "keep_page_markers": options.keep_page_markers,
        "remove_header_footer": options.remove_header_footer,
        "dedupe_images": options.dedupe_images,
        "repair_hyphenation": options.repair_hyphenation,
        "figure_crop_fallback": options.figure_crop_fallback,
        "page_workers": options.page_workers,
        "debug": options.debug,
        "verbose": options.verbose,
        "skip_existing": options.skip_existing,
    }


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
    stem = pdf_path.stem
    return Config(
        input_pdf=pdf_path,
        output_dir=output_root / stem,
        markdown_filename=f"{stem}.md",
        manifest_filename=f"{stem}_manifest.json",
        report_filename=f"{stem}_report.json",
        assets_dirname=f"{stem}_assets",
        **_coerce_options(request.options),
    )


def iter_pdf_paths(input_dir: Path) -> list[Path]:
    """Return direct child PDF files in deterministic order."""
    return sorted(
        [path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"],
        key=lambda path: (path.name.lower(), path.name),
    )


def _detect_duplicate_stems(pdf_paths: list[Path]) -> list[str]:
    stem_map: dict[str, list[str]] = {}
    for path in pdf_paths:
        stem_map.setdefault(path.stem.casefold(), []).append(path.name)
    return sorted(", ".join(sorted(names)) for names in stem_map.values() if len(names) > 1)


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
        warning_codes=warning_codes_for_display(result.warnings),
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


def _run_single(request: GuiConversionRequest, progress: ProgressCallback | None) -> GuiConversionSummary:
    config = build_single_config(request)
    _emit(progress, f"Converting {config.input_pdf}")
    result = run_conversion(config)
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


def _run_batch(
    request: GuiConversionRequest,
    progress: ProgressCallback | None,
    batch_progress: BatchProgressCallback | None,
    cancel_requested: CancelCallback | None,
) -> GuiConversionSummary:
    input_dir = request.input_path
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist or is not a directory: {input_dir}")
    pdf_paths = iter_pdf_paths(input_dir)
    if not pdf_paths:
        raise ValueError(f"No PDF files found in directory: {input_dir}")
    duplicates = _detect_duplicate_stems(pdf_paths)
    if duplicates:
        raise ValueError(f"Duplicate PDF stems found: {'; '.join(duplicates)}")

    output_root = request.output_dir if request.output_dir is not None else input_dir / "output"
    output_root.mkdir(parents=True, exist_ok=True)
    documents: list[GuiDocumentSummary] = []
    exit_code = 0
    option_fingerprint = gui_options_fingerprint(request.options)
    total = len(pdf_paths)
    for index, pdf_path in enumerate(pdf_paths, start=1):
        config = build_batch_config(request, pdf_path, output_root)
        if cancel_requested is not None and cancel_requested():
            exit_code = EXIT_PARTIAL
            for cancelled_path in pdf_paths[index - 1 :]:
                cancelled_config = build_batch_config(request, cancelled_path, output_root)
                _emit(progress, f"Cancelled {cancelled_path.name}: request received before conversion")
                _emit_batch_progress(
                    batch_progress,
                    current=pdf_paths.index(cancelled_path) + 1,
                    total=total,
                    input_pdf=cancelled_path,
                    status=GUI_STATUS_CANCELLED,
                )
                documents.append(_cancelled_document_summary(cancelled_config, option_fingerprint))
            break
        if request.options.skip_existing and _has_existing_core_outputs(config):
            _emit(progress, f"Skipped {pdf_path.name}: existing core outputs")
            _emit_batch_progress(
                batch_progress,
                current=index,
                total=total,
                input_pdf=pdf_path,
                status=GUI_STATUS_SKIPPED,
            )
            documents.append(
                GuiDocumentSummary(
                    input_pdf=pdf_path,
                    output_dir=config.output_dir,
                    status=GUI_STATUS_SKIPPED,
                    exit_code=0,
                    markdown_path=_markdown_path(config),
                    manifest_path=_manifest_path(config),
                    report_path=_report_path(config),
                    assets_dir=_assets_dir(config),
                    skipped=True,
                    option_fingerprint=option_fingerprint,
                    message="existing core outputs",
                )
            )
            continue
        _emit(progress, f"Converting {pdf_path}")
        _emit_batch_progress(
            batch_progress,
            current=index,
            total=total,
            input_pdf=pdf_path,
            status="started",
        )
        try:
            result = run_conversion(config)
        except Exception as exc:  # noqa: BLE001
            exit_code = EXIT_PARTIAL
            _emit(progress, f"Failed {pdf_path.name}: {exc}")
            _emit_batch_progress(
                batch_progress,
                current=index,
                total=total,
                input_pdf=pdf_path,
                status=ConversionStatus.FAILED.value,
            )
            documents.append(_failed_document_summary(config, exc, option_fingerprint))
            continue
        _emit(progress, f"Finished {pdf_path.name}: {result.status.value}")
        _emit_batch_progress(
            batch_progress,
            current=index,
            total=total,
            input_pdf=pdf_path,
            status=result.status.value,
        )
        if result.exit_code != 0:
            exit_code = EXIT_PARTIAL
        documents.append(_document_summary_from_result(config, result, option_fingerprint=option_fingerprint))
    return GuiConversionSummary(
        input_mode="folder",
        input_path=input_dir,
        output_root=output_root,
        documents=documents,
        exit_code=exit_code,
    )


def run_gui_conversion(
    request: GuiConversionRequest,
    *,
    progress: ProgressCallback | None = None,
    batch_progress: BatchProgressCallback | None = None,
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
        return _run_single(request, progress)
    if mode == "folder":
        return _run_batch(request, progress, batch_progress, cancel_requested)
    raise ValueError(f"Unsupported GUI input mode: {request.input_mode}")
