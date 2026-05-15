from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pdf2md.config import Config, default_output_dir_for_input
from pdf2md.models import ConversionStatus, DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode
from pdf2md.pipeline import EXIT_PARTIAL, run_conversion


ProgressCallback = Callable[[str], None]


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
class GuiDocumentSummary:
    input_pdf: Path
    output_dir: Path
    status: str
    exit_code: int
    skipped: bool = False
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
        key=lambda path: path.name.lower(),
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


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _run_single(request: GuiConversionRequest, progress: ProgressCallback | None) -> GuiConversionSummary:
    config = build_single_config(request)
    _emit(progress, f"Converting {config.input_pdf}")
    result = run_conversion(config)
    _emit(progress, f"Finished {config.input_pdf.name}: {result.status.value}")
    document = GuiDocumentSummary(
        input_pdf=config.input_pdf,
        output_dir=config.output_dir,
        status=result.status.value,
        exit_code=result.exit_code,
    )
    return GuiConversionSummary(
        input_mode="file",
        input_path=request.input_path,
        output_root=config.output_dir,
        documents=[document],
        exit_code=result.exit_code,
    )


def _run_batch(request: GuiConversionRequest, progress: ProgressCallback | None) -> GuiConversionSummary:
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
    for pdf_path in pdf_paths:
        config = build_batch_config(request, pdf_path, output_root)
        if request.options.skip_existing and _has_existing_core_outputs(config):
            _emit(progress, f"Skipped {pdf_path.name}: existing core outputs")
            documents.append(
                GuiDocumentSummary(
                    input_pdf=pdf_path,
                    output_dir=config.output_dir,
                    status="skipped",
                    exit_code=0,
                    skipped=True,
                    message="existing core outputs",
                )
            )
            continue
        _emit(progress, f"Converting {pdf_path}")
        result = run_conversion(config)
        _emit(progress, f"Finished {pdf_path.name}: {result.status.value}")
        if result.exit_code != 0:
            exit_code = EXIT_PARTIAL
        documents.append(
            GuiDocumentSummary(
                input_pdf=pdf_path,
                output_dir=config.output_dir,
                status=result.status.value,
                exit_code=result.exit_code,
            )
        )
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
) -> GuiConversionSummary:
    """Run a GUI-initiated conversion through the same core pipeline as CLI conversions."""
    mode = request.input_mode.lower()
    if mode == "file":
        if not request.input_path.exists() or not request.input_path.is_file():
            raise ValueError(f"Input PDF does not exist or is not a file: {request.input_path}")
        if request.input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {request.input_path}")
        return _run_single(request, progress)
    if mode == "folder":
        return _run_batch(request, progress)
    raise ValueError(f"Unsupported GUI input mode: {request.input_mode}")
