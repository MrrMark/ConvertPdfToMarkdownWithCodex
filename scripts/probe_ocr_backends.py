#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.models import OCRBackendProbeReport
from pdf2md.utils.io import write_json

try:
    from scripts.check_ocr_runtime import (
        _discover_tesseract,
        _list_tesseract_languages,
        _module_available,
        _split_ocr_lang,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from check_ocr_runtime import (  # type: ignore[no-redef]
        _discover_tesseract,
        _list_tesseract_languages,
        _module_available,
        _split_ocr_lang,
    )


@dataclass(frozen=True)
class BackendSpec:
    name: str
    modules: tuple[str, ...] = ()
    executable: str | None = None
    requires_pypdfium2: bool = True
    checks_tesseract_languages: bool = False
    platform_name: str | None = None
    raw_confidence_unit: str = "unknown"
    normalized_confidence_unit: str = "0_to_1"
    notes: str = ""


BACKEND_SPECS: tuple[BackendSpec, ...] = (
    BackendSpec(
        name="tesseract",
        modules=("pytesseract",),
        executable="tesseract",
        checks_tesseract_languages=True,
        raw_confidence_unit="0_to_100",
        notes="Current default OCR path through pytesseract plus pypdfium2 rendering.",
    ),
    BackendSpec(
        name="tesseract-cli",
        executable="tesseract",
        checks_tesseract_languages=True,
        raw_confidence_unit="0_to_100",
        notes="System Tesseract executable conversion path without Python pytesseract import.",
    ),
    BackendSpec(
        name="rapidocr",
        modules=("rapidocr_onnxruntime", "rapidocr"),
        raw_confidence_unit="0_to_1",
        notes="Optional RapidOCR Python backend; not used by the default converter.",
    ),
    BackendSpec(
        name="easyocr",
        modules=("easyocr",),
        raw_confidence_unit="0_to_1",
        notes="Optional EasyOCR Python backend; not used by the default converter.",
    ),
    BackendSpec(
        name="ocrmac",
        modules=("ocrmac",),
        platform_name="Darwin",
        raw_confidence_unit="backend_specific",
        notes="Optional macOS Vision OCR wrapper; only supported on macOS.",
    ),
    BackendSpec(
        name="docling",
        modules=("docling",),
        requires_pypdfium2=False,
        raw_confidence_unit="backend_specific",
        notes="Optional Docling pipeline probe, not a replacement for the default OCR path.",
    ),
)


def _selected_specs(raw_backends: str) -> list[BackendSpec]:
    by_name = {spec.name: spec for spec in BACKEND_SPECS}
    if raw_backends.strip() == "all":
        return list(BACKEND_SPECS)
    selected: list[BackendSpec] = []
    seen: set[str] = set()
    for raw_backend in raw_backends.split(","):
        backend = raw_backend.strip()
        if not backend or backend in seen:
            continue
        if backend not in by_name:
            raise ValueError(f"Unknown OCR backend: {backend}")
        selected.append(by_name[backend])
        seen.add(backend)
    return selected or list(BACKEND_SPECS)


def _first_available_module(modules: tuple[str, ...]) -> tuple[str | None, bool]:
    for module_name in modules:
        if _module_available(module_name):
            return module_name, True
    return (modules[0], False) if modules else (None, True)


def _executable_path(name: str | None) -> str | None:
    if name is None:
        return None
    if name == "tesseract":
        return _discover_tesseract()
    return shutil.which(name)


def _dependency(name: str, kind: str, available: bool, detail: str | None = None) -> dict[str, Any]:
    return {"name": name, "kind": kind, "available": available, "detail": detail}


def _probe_backend(spec: BackendSpec, requested_languages: list[str]) -> dict[str, Any]:
    dependencies: list[dict[str, Any]] = []
    hints: list[str] = []
    platform_supported = spec.platform_name is None or platform.system() == spec.platform_name
    module_name, module_available = _first_available_module(spec.modules)
    executable = _executable_path(spec.executable)
    executable_available = executable is not None if spec.executable else None

    if spec.modules:
        dependencies.append(_dependency(module_name or spec.modules[0], "module", module_available))
        if not module_available:
            hints.append(f"Install optional OCR backend package for {spec.name}: {', '.join(spec.modules)}.")
    if spec.executable:
        dependencies.append(_dependency(spec.executable, "executable", bool(executable), executable))
        if executable is None:
            hints.append(f"Install {spec.executable} and make sure it is on PATH.")
    if spec.requires_pypdfium2:
        pypdfium2_available = _module_available("pypdfium2")
        dependencies.append(_dependency("pypdfium2", "module", pypdfium2_available))
        if not pypdfium2_available:
            hints.append("Install pypdfium2 for deterministic PDF page rendering before OCR.")
    if not platform_supported:
        hints.append(f"{spec.name} is only supported on {spec.platform_name}.")

    language_data = {
        "checked": False,
        "requested": requested_languages,
        "available": [],
        "missing": [],
        "error": None,
    }
    if spec.checks_tesseract_languages:
        available_languages, language_error = _list_tesseract_languages(executable)
        missing_languages = [lang for lang in requested_languages if lang not in available_languages]
        language_data = {
            "checked": True,
            "requested": requested_languages,
            "available": available_languages,
            "missing": missing_languages,
            "error": language_error,
        }
        if missing_languages:
            hints.append("Install missing Tesseract language data: " + ", ".join(missing_languages) + ".")
        if language_error:
            hints.append(language_error)

    dependency_ready = all(item["available"] for item in dependencies)
    language_ready = not language_data["checked"] or (not language_data["missing"] and language_data["error"] is None)
    ready = bool(platform_supported and dependency_ready and language_ready)
    module_dependency_available = True if not spec.modules else module_available
    executable_dependency_available = True if spec.executable is None else bool(executable)
    available = bool(platform_supported and module_dependency_available and executable_dependency_available)
    status = "ready" if ready else "available" if available else "unavailable"

    return {
        "backend": spec.name,
        "status": status,
        "ready": ready,
        "module": module_name,
        "module_available": module_available if spec.modules else None,
        "executable": executable,
        "executable_available": executable_available,
        "platform_supported": platform_supported,
        "confidence_normalization": {
            "raw_unit": spec.raw_confidence_unit,
            "normalized_unit": spec.normalized_confidence_unit,
            "higher_is_better": True,
        },
        "language_data": language_data,
        "dependencies": dependencies,
        "hints": hints,
    }


def probe_ocr_backends(
    *,
    ocr_lang: str = "eng",
    backends: str = "all",
    require_ready: bool = False,
) -> dict[str, Any]:
    """Probe optional OCR backend availability without running OCR on document content."""
    requested_languages = _split_ocr_lang(ocr_lang)
    records = [_probe_backend(spec, requested_languages) for spec in _selected_specs(backends)]
    ready_backends = [record["backend"] for record in records if record["ready"]]
    unavailable_backends = [record["backend"] for record in records if record["status"] == "unavailable"]
    summary = {
        "total_backend_count": len(records),
        "available_backend_count": sum(1 for record in records if record["status"] in {"available", "ready"}),
        "ready_backend_count": len(ready_backends),
        "requested_languages": requested_languages,
        "ready_backends": ready_backends,
        "unavailable_backends": unavailable_backends,
        "recommended_backend": ready_backends[0] if ready_backends else None,
        "require_ready": require_ready,
    }
    payload = {
        "schema_version": "1.0",
        "purpose": "multi_ocr_backend_probe",
        "ocr_lang": ocr_lang,
        "local_only": True,
        "raw_content_included": False,
        "image_bytes_included": False,
        "customer_paths_included": False,
        "summary": summary,
        "backends": records,
    }
    return OCRBackendProbeReport.model_validate(payload).model_dump(mode="json")


def format_text_report(report: dict[str, Any]) -> str:
    """Render a compact human-readable OCR backend probe report."""
    lines = [
        "OCR backend probe",
        f"- OCR language: {report['ocr_lang']}",
        f"- Ready backends: {', '.join(report['summary']['ready_backends']) or 'none'}",
        f"- Recommended backend: {report['summary']['recommended_backend'] or 'none'}",
        "",
        "| Backend | Status | Ready | Module | Executable |",
        "| --- | --- | --- | --- | --- |",
    ]
    for backend in report["backends"]:
        lines.append(
            "| {backend} | {status} | {ready} | {module} | {executable} |".format(
                backend=backend["backend"],
                status=backend["status"],
                ready="yes" if backend["ready"] else "no",
                module=backend.get("module") or "",
                executable=backend.get("executable") or "",
            )
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe optional OCR backend availability without running OCR.")
    parser.add_argument("--ocr-lang", default="eng", help="OCR language request, for example eng or kor+eng.")
    parser.add_argument(
        "--backends",
        default="all",
        help="Comma-separated backends to probe, or all. Supported: tesseract,tesseract-cli,rapidocr,easyocr,ocrmac,docling.",
    )
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Shortcut for --format json.")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero when no selected backend is ready.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = probe_ocr_backends(
            ocr_lang=args.ocr_lang,
            backends=args.backends,
            require_ready=args.require_ready,
        )
    except ValueError as exc:
        print(str(exc))
        return 2

    if args.report_file is not None:
        write_json(args.report_file, report)
    output_format = "json" if args.json_output else args.format
    if output_format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_text_report(report), end="")
    if args.require_ready and not report["summary"]["ready_backend_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
