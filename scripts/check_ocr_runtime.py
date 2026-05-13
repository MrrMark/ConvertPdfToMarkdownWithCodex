#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _discover_tesseract() -> str | None:
    executable = shutil.which("tesseract")
    if executable:
        return executable
    homebrew_tesseract = Path("/opt/homebrew/bin/tesseract")
    if homebrew_tesseract.exists():
        return str(homebrew_tesseract)
    return None


def _split_ocr_lang(ocr_lang: str) -> list[str]:
    languages: list[str] = []
    seen: set[str] = set()
    for raw_lang in ocr_lang.split("+"):
        lang = raw_lang.strip()
        if not lang or lang in seen:
            continue
        languages.append(lang)
        seen.add(lang)
    return languages


def _list_tesseract_languages(executable: str | None) -> tuple[list[str], str | None]:
    if executable is None:
        return [], "Tesseract executable was not found."
    try:
        completed = subprocess.run(
            [executable, "--list-langs"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        return [], f"Failed to run tesseract --list-langs: {exc}"

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    languages: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower_line = line.lower()
        if lower_line.startswith("list of available languages"):
            continue
        if lower_line.startswith("error"):
            continue
        languages.append(line)
    if completed.returncode != 0:
        return languages, f"tesseract --list-langs exited with code {completed.returncode}."
    return sorted(set(languages)), None


def check_ocr_runtime(ocr_lang: str = "eng") -> dict[str, Any]:
    """Inspect OCR runtime dependencies and requested Tesseract language data."""
    executable = _discover_tesseract()
    requested_languages = _split_ocr_lang(ocr_lang)
    available_languages, language_error = _list_tesseract_languages(executable)
    missing_languages = [lang for lang in requested_languages if lang not in available_languages]
    pytesseract_available = _module_available("pytesseract")
    pypdfium2_available = _module_available("pypdfium2")

    hints: list[str] = []
    if executable is None:
        hints.append("Install Tesseract and make sure the tesseract executable is on PATH.")
    if not pytesseract_available:
        hints.append("Install the Python package pytesseract.")
    if not pypdfium2_available:
        hints.append("Install the Python package pypdfium2.")
    if missing_languages:
        hints.append(
            "Install missing Tesseract language data: "
            + ", ".join(missing_languages)
            + ". For Korean OCR, install kor and use --ocr-lang kor+eng."
        )

    ready = bool(executable and pytesseract_available and pypdfium2_available and not missing_languages and language_error is None)
    return {
        "ocr_lang": ocr_lang,
        "ready": ready,
        "checks": {
            "tesseract_executable": {
                "ok": executable is not None,
                "path": executable,
            },
            "pytesseract_import": {
                "ok": pytesseract_available,
            },
            "pypdfium2_import": {
                "ok": pypdfium2_available,
            },
            "language_data": {
                "ok": not missing_languages and language_error is None,
                "requested": requested_languages,
                "available": available_languages,
                "missing": missing_languages,
                "error": language_error,
            },
        },
        "hints": hints,
    }


def format_text_report(report: dict[str, Any]) -> str:
    """Render a human-readable OCR runtime check report."""
    checks = report["checks"]
    language_data = checks["language_data"]
    lines = [
        "OCR runtime check",
        f"- OCR language: {report['ocr_lang']}",
        "- Tesseract executable: "
        + ("OK (" + str(checks["tesseract_executable"]["path"]) + ")" if checks["tesseract_executable"]["ok"] else "MISSING"),
        "- pytesseract import: " + ("OK" if checks["pytesseract_import"]["ok"] else "MISSING"),
        "- pypdfium2 import: " + ("OK" if checks["pypdfium2_import"]["ok"] else "MISSING"),
        "- Tesseract language data: " + ("OK" if language_data["ok"] else "MISSING"),
    ]
    if language_data["requested"]:
        lines.append("- Requested languages: " + ", ".join(language_data["requested"]))
    if language_data["missing"]:
        lines.append("- Missing languages: " + ", ".join(language_data["missing"]))
    if language_data["error"]:
        lines.append("- Language check error: " + str(language_data["error"]))
    if report["hints"]:
        lines.append("")
        lines.append("Recommended fixes:")
        lines.extend(f"- {hint}" for hint in report["hints"])
    lines.append("")
    lines.append("Ready: " + ("yes" if report["ready"] else "no"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OCR runtime and Tesseract language data.")
    parser.add_argument("--ocr-lang", default="eng", help="Tesseract language code, for example eng or kor+eng.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Shortcut for --format json.")
    args = parser.parse_args()

    output_format = "json" if args.json_output else args.format
    report = check_ocr_runtime(args.ocr_lang)
    if output_format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_text_report(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
