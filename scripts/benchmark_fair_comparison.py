"""Q156 local CPU benchmark: independent engine processes, one cold and five warm runs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WARM_RUNS = 5
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OMP_THREAD_LIMIT",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def file_hash(path: Path) -> str:
    """Hash source/model bytes without including their content in the report."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def model_identity(path: Path, suffix: str | None = None) -> dict:
    """Identify local model revisions by a deterministic content-tree hash."""
    digest = hashlib.sha256()
    count = 0
    for item in sorted(path.rglob("*")):
        if item.is_file() and (suffix is None or item.suffix == suffix):
            digest.update(item.relative_to(path).as_posix().encode() + b"\0")
            digest.update(file_hash(item).encode() + b"\n")
            count += 1
    return {"file_count": count, "tree_sha256": digest.hexdigest()}


def ocr_identity() -> dict:
    """Record the local English Tesseract model and executable when discoverable."""
    try:
        version = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=10, check=True)
        languages = subprocess.run(
            ["tesseract", "--list-langs"], capture_output=True, text=True, timeout=10, check=True
        )
        match = re.search(r'"([^"\n]+)"', languages.stdout + languages.stderr)
        trained = Path(match[1]) / "eng.traineddata" if match else None
        return {
            "version": (version.stdout or version.stderr).splitlines()[0],
            "language": "eng",
            "model_sha256": file_hash(trained) if trained and trained.is_file() else None,
        }
    except (OSError, subprocess.SubprocessError, IndexError):
        return {"version": None, "language": "eng", "model_sha256": None}


def peak_rss() -> dict:
    """Report process-lifetime peak RSS; unavailable platforms return null."""
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "bytes": int(value if sys.platform == "darwin" else value * 1024),
            "scope": "engine_process_lifetime_excludes_children",
            "method": "getrusage",
        }
    except ImportError:
        return {"bytes": None, "scope": "unavailable", "method": None}


def summarize_runs(runs: list[dict]) -> dict:
    """Aggregate exactly five successful warm samples, never a small-sample p95."""
    warm = [r["convert_export_write_seconds"] for r in runs if r["phase"] == "warm" and r["status"] == "success"]
    complete = len(warm) == WARM_RUNS
    return {
        "warm_success_count": len(warm),
        "warm_complete": complete,
        "warm_median_seconds": statistics.median(warm) if complete else None,
        "warm_min_seconds": min(warm) if complete else None,
        "warm_max_seconds": max(warm) if complete else None,
    }


def docling_counts(document: object) -> dict:
    """Count actual document collections, never matching exported key names."""
    return {name: len(getattr(document, name)) for name in ("tables", "pictures", "pages")}


def native_config(request: dict, output: Path):
    """Resolve the same CLI profile defaults used by normal conversion."""
    from pdf2md.cli import build_parser, _build_single_config

    argv = [
        request["input_pdf"],
        "-o",
        str(output),
        "--rag-profile",
        request["native_profile"],
        "--domain-adapter",
        request["domain_adapter"],
        "--page-workers",
        "1",
    ]
    return _build_single_config(build_parser().parse_args(argv))


def engine_worker(request: dict) -> dict:
    """Initialize one engine and run six fresh-output conversions in its own process."""
    engine = request["engine"]
    report = {
        "engine": engine,
        "status": "failed",
        "pid": os.getpid(),
        "runs": [],
        "input_sha256": file_hash(Path(request["input_pdf"])),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "worker_count": 1,
            "threads_requested": request["threads"],
            "thread_environment": {key: os.environ.get(key) for key in THREAD_VARIABLES},
        },
        "quality": {"status": "not_evaluated", "reason": "requires_separate_source_truth"},
        "features": {
            "markdown": "supported",
            "native_rag_sidecars": "supported" if engine == "native" else "unsupported",
        },
        "model_download": {"status": "disabled", "seconds": None},
    }
    stage = "import"
    started = time.perf_counter()
    try:
        if request.get("expected_package"):
            actual = importlib.metadata.version(request["expected_package"])
            report["version_check"] = {"expected": request["expected_version"], "actual": actual}
            if actual != request["expected_version"]:
                report["unavailable_reason"] = "pinned_version_mismatch"
                raise ImportError("pinned_version_mismatch")
        if engine == "native":
            from pdf2md.pipeline import run_conversion
            from pdf2md.cli import build_parser  # noqa: F401
        elif engine == "docling":
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
            from docling.datamodel.accelerator_options import AcceleratorOptions
        else:
            from scripts.benchmark_external_cpu import prepare_external
            convert_external, external_info = prepare_external(engine, request)
            report.update(external_info)
        report["import_seconds"] = time.perf_counter() - started
        packages = (
            ["pdf2md", "pdfplumber", "pypdf", "pypdfium2"]
            if engine == "native"
            else ["docling", "docling-core", "torch", "transformers"] if engine == "docling"
            else ["pymupdf4llm", "pymupdf", "pymupdf-layout", "onnxruntime"] if engine == "pymupdf"
            else ["marker-pdf", "surya-ocr"]
        )
        report["packages"] = {}
        for package in packages:
            try:
                report["packages"][package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                report["packages"][package] = None
        stage = "setup"
        started = time.perf_counter()
        report["ocr_runtime"] = ocr_identity()
        if engine == "native":
            report["source_code_identity"] = model_identity(ROOT / "pdf2md", suffix=".py")
            config = native_config(request, Path(request["output"]) / "cold")
            report["effective_options"] = config.model_dump(
                mode="json", exclude={"input_pdf", "output_dir", "password"}
            )
        elif engine == "docling":
            artifacts = Path(request["models"]) if request.get("models") else None
            if artifacts is None or not artifacts.is_dir():
                report['unavailable_reason'] = 'local_model_directory_required'
                raise FileNotFoundError("local_models_required")
            report["models"] = model_identity(artifacts)
            if report["models"]["file_count"] == 0:
                report['unavailable_reason'] = 'local_model_directory_empty'
                raise FileNotFoundError("empty_model_directory")
            options = PdfPipelineOptions(
                artifacts_path=artifacts,
                ocr_options=TesseractCliOcrOptions(lang=["eng"]),
                enable_remote_services=False,
                accelerator_options=AcceleratorOptions(device="cpu", num_threads=request["threads"]),
            )
            report["effective_options"] = options.model_dump(mode="json", exclude={"artifacts_path"})
            converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
            converter.initialize_pipeline(InputFormat.PDF)
        report["setup_seconds"] = time.perf_counter() - started
        stage = "conversion"
        for index in range(WARM_RUNS + 1):
            output = Path(request["output"]) / ("cold" if index == 0 else f"warm-{index}")
            output.mkdir(exist_ok=False, parents=True)
            run = {"phase": "cold" if index == 0 else "warm", "index": index, "status": "failed"}
            started = time.perf_counter()
            try:
                if engine == "native":
                    result = run_conversion(config.model_copy(update={"output_dir": output}))
                    run["status"] = (
                        "success" if result.exit_code == 0 else "partial_success" if result.exit_code == 2 else "failed"
                    )
                elif engine == "docling":
                    result = converter.convert(request["input_pdf"])
                    document = result.document
                    (output / "document.md").write_text(document.export_to_markdown(), encoding="utf-8")
                    (output / "document.json").write_text(
                        json.dumps(document.export_to_dict(), ensure_ascii=False), encoding="utf-8"
                    )
                    run["status"] = (
                        "success"
                        if str(getattr(result.status, "value", result.status)) == "success"
                        else "partial_success"
                    )
                else:
                    external_counts = convert_external(Path(request["input_pdf"]), output)
                    run["status"] = "success"
                run["convert_export_write_seconds"] = time.perf_counter() - started
                if engine == "native":
                    manifest = json.loads((output / "manifest.json").read_text())
                    run["counts"] = {
                        "tables": len(manifest["tables"]),
                        "pictures": len(manifest["images"]),
                        "pages": len(manifest["selected_pages"]),
                    }
                    run["effective_options"] = manifest["options"]
                elif engine == "docling":
                    run["counts"] = docling_counts(document)
                else:
                    run["counts"] = external_counts
                run["pages_per_second"] = run["counts"]["pages"] / run["convert_export_write_seconds"]
            except Exception as exc:
                run["status"] = "failed"
                run["error_type"] = type(exc).__name__
                run["convert_export_write_seconds"] = time.perf_counter() - started
            report["runs"].append(run)
        report["summary"] = summarize_runs(report["runs"])
        report["status"] = "success" if all(r["status"] == "success" for r in report["runs"]) else "incomplete"
    except Exception as exc:
        if getattr(exc, "reason", None):
            report["unavailable_reason"] = exc.reason
        report["error"] = {"stage": stage, "type": type(exc).__name__}
        report["status"] = "unavailable" if isinstance(exc, (ImportError, FileNotFoundError)) else "failed"
        report[f"{stage}_seconds"] = time.perf_counter() - started
    report["peak_rss"] = peak_rss()
    return report


def run_benchmark(args: argparse.Namespace) -> dict:
    """Materialize one shared slice and execute each engine in a separate interpreter."""
    from pypdf import PdfReader, PdfWriter
    from pdf2md.utils.page_range import parse_page_range

    source = args.input_pdf.resolve()
    preparation_started = time.perf_counter()
    reader = PdfReader(source)
    pages = parse_page_range(args.pages, len(reader.pages))
    if not pages:
        raise ValueError("empty input PDF")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    shared = args.output_dir.resolve() / "input.pdf"
    # Already sliced corpora need no rewrite. Copying preserves their bytes and
    # avoids recursively cloning unrelated cross-page PDF resource graphs.
    preparation_method = "byte_copy" if pages == list(range(1, len(reader.pages) + 1)) else "pypdf_slice"
    if preparation_method == "byte_copy":
        shutil.copyfile(source, shared)
    else:
        writer = PdfWriter()
        for number in pages:
            writer.add_page(reader.pages[number - 1])
        writer.write(shared)
    report = {
        "schema_version": "1.0",
        "purpose": "fair_conversion_benchmark",
        "source_sha256": file_hash(source),
        "slice_sha256": file_hash(shared),
        "source_pages": pages,
        "input_preparation_seconds": time.perf_counter() - preparation_started,
        "method": {
            "cold_runs": 1,
            "warm_runs": WARM_RUNS,
            "cold_definition": "first_conversion_after_explicit_setup",
            "warm_definition": "same_process_and_engine_fresh_output_directory",
            "timed_region": "convert_export_write",
            "os_cache_cleared": False,
            "download_policy": "preprovisioned_local_models_only",
            "input_preparation_method": preparation_method,
        },
        "engines": [],
    }
    for engine in args.engines:
        request = {
            "engine": engine,
            "input_pdf": str(shared),
            "output": str(args.output_dir.resolve() / engine),
            "native_profile": args.native_profile,
            "domain_adapter": args.domain_adapter,
            "threads": args.threads,
            "models": str(args.docling_models.resolve()) if args.docling_models else None,
        }
        if getattr(args, "fixed_external_versions", False) and engine != "native":
            from scripts.benchmark_external_cpu import PINS
            request["expected_package"], request["expected_version"] = PINS[engine]
        request_path = args.output_dir.resolve() / f"{engine}.request.json"
        result_path = args.output_dir.resolve() / f"{engine}.result.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        interpreter = getattr(args, f"{engine}_python", sys.executable) if engine != "native" else sys.executable
        env = {
            **os.environ,
            **{key: str(args.threads) for key in THREAD_VARIABLES},
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
        start = time.perf_counter()
        try:
            completed = subprocess.run(
                [
                    interpreter,
                    str(Path(__file__).resolve()),
                    "--worker",
                    str(request_path),
                    "--result",
                    str(result_path),
                ],
                env=env,
                cwd=ROOT,
                capture_output=True,
                timeout=args.timeout,
            )
            data = (
                json.loads(result_path.read_text())
                if completed.returncode == 0 and result_path.is_file()
                else {
                    "engine": engine,
                    "status": "failed",
                    "error": {"stage": "process", "returncode": completed.returncode},
                }
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            data = {"engine": engine, "status": "failed", "error": {"stage": "process", "type": type(exc).__name__}}
        data["process_wall_seconds"] = time.perf_counter() - start
        if data.get("input_sha256") != report["slice_sha256"]:
            data["status"] = "failed"
            data["input_identity_verified"] = False
        else:
            data["input_identity_verified"] = True
        report["engines"].append(data)
    report["timing_samples_complete"] = all(e["status"] == "success" for e in report["engines"])
    report["feature_parity_assumed"] = False
    from pdf2md.benchmark_models import FairBenchmarkReport

    report = FairBenchmarkReport.model_validate(report).model_dump(mode="json")
    (args.output_dir / "fair_benchmark_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    """Run the isolated benchmark or its private worker protocol."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--input-pdf", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--pages")
    parser.add_argument("--engines", nargs="+", choices=["native", "docling", "pymupdf", "marker"], default=["native", "docling"])
    parser.add_argument("--fixed-external-versions", action="store_true")
    parser.add_argument("--pymupdf-python", default=sys.executable)
    parser.add_argument("--marker-python", default=sys.executable)
    parser.add_argument("--native-profile", default="technical_spec_rag_visual")
    parser.add_argument("--domain-adapter", default="none")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--docling-python", default=sys.executable)
    parser.add_argument("--docling-models", type=Path)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    if args.worker:
        if args.result is None:
            parser.error("--worker requires --result")
        args.result.write_text(
            json.dumps(engine_worker(json.loads(args.worker.read_text())), indent=2) + "\n", encoding="utf-8"
        )
        return 0
    if not args.input_pdf or not args.output_dir or args.threads < 1 or args.timeout <= 0:
        parser.error("input-pdf, new output-dir, positive threads and timeout are required")
    if len(set(args.engines)) != len(args.engines):
        parser.error("duplicate engines are not allowed")
    report = run_benchmark(args)
    return 0 if report["timing_samples_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
