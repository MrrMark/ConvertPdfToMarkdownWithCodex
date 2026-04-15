from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_output_dirs(output_dir: Path, assets_dirname: str = "assets") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / assets_dirname).mkdir(parents=True, exist_ok=True)
    (output_dir / assets_dirname / "images").mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_output_bundle(
    output_dir: Path,
    *,
    markdown_filename: str = "document.md",
    manifest_filename: str = "manifest.json",
    report_filename: str = "report.json",
    expected_schema_version: str = "1.0",
) -> list[str]:
    """Validate the minimum output bundle structure without mutating repo state."""
    errors: list[str] = []
    markdown_path = output_dir / markdown_filename
    manifest_path = output_dir / manifest_filename
    report_path = output_dir / report_filename

    for path in (markdown_path, manifest_path, report_path):
        if not path.exists():
            errors.append(f"Missing required output: {path.name}")

    if errors:
        return errors

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != expected_schema_version:
        errors.append(f"manifest schema_version mismatch: {manifest.get('schema_version')}")
    if report.get("schema_version") != expected_schema_version:
        errors.append(f"report schema_version mismatch: {report.get('schema_version')}")
    return errors
