#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, StreamObject

from pdf2md.gui_runner import GuiConversionOptions, GuiConversionRequest, run_gui_conversion
from pdf2md.utils.io import write_json


PARITY_REPORT = "gui_cli_parity_report.json"
PARITY_ARTIFACTS = (
    "document.md",
    "manifest.json",
    "report.json",
    "text_blocks_rag.jsonl",
    "semantic_units_rag.jsonl",
    "requirements_rag.jsonl",
    "cross_refs_rag.jsonl",
    "requirement_traceability_rag.jsonl",
    "technical_tables_rag.jsonl",
    "retrieval_chunks_rag.jsonl",
    "figures_rag.jsonl",
)
DYNAMIC_JSON_KEYS = {
    "started_at",
    "finished_at",
    "duration_ms",
    "stage_durations_ms",
    "pages_per_second",
}


def write_parity_fixture(path: Path) -> None:
    """Write a small deterministic PDF fixture for CLI/GUI output parity checks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)  # noqa: SLF001
    page = writer.add_blank_page(width=595, height=842)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    text = "BT /F1 12 Tf 72 760 Td (Q74 GUI CLI parity fixture shall preserve text.) Tj ET"
    content = StreamObject()
    content._data = zlib.compress(text.encode("utf-8"))  # noqa: SLF001
    content[NameObject("/Filter")] = NameObject("/FlateDecode")
    content[NameObject("/Length")] = NumberObject(len(content._data))  # noqa: SLF001
    page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001
    with path.open("wb") as handle:
        writer.write(handle)


def normalized_artifact_hash(path: Path) -> str:
    """Return a deterministic hash while ignoring report timing fields."""
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = json.dumps(_normalize_json(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    elif path.suffix == ".jsonl":
        records = [
            json.dumps(_normalize_json(json.loads(line)), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        data = ("\n".join(records) + ("\n" if records else "")).encode("utf-8")
    else:
        data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def compare_artifacts(
    cli_output_dir: Path,
    gui_output_dir: Path,
    artifact_names: tuple[str, ...] = PARITY_ARTIFACTS,
) -> dict[str, Any]:
    """Compare normalized CLI and GUI artifacts without storing raw document content."""
    artifacts: list[dict[str, Any]] = []
    for artifact_name in artifact_names:
        cli_path = cli_output_dir / artifact_name
        gui_path = gui_output_dir / artifact_name
        cli_exists = cli_path.exists()
        gui_exists = gui_path.exists()
        cli_hash = normalized_artifact_hash(cli_path) if cli_exists else None
        gui_hash = normalized_artifact_hash(gui_path) if gui_exists else None
        artifacts.append(
            {
                "artifact": artifact_name,
                "status": "matched" if cli_exists and gui_exists and cli_hash == gui_hash else "mismatched",
                "cli_exists": cli_exists,
                "gui_exists": gui_exists,
                "cli_sha256": cli_hash,
                "gui_sha256": gui_hash,
            }
        )
    mismatches = [artifact for artifact in artifacts if artifact["status"] != "matched"]
    return {
        "artifacts": artifacts,
        "summary": {
            "checked_count": len(artifacts),
            "matched_count": len(artifacts) - len(mismatches),
            "mismatched_count": len(mismatches),
        },
        "passed": not mismatches,
    }


def run_parity(output_dir: Path) -> dict[str, Any]:
    """Run CLI and GUI conversions over the same fixture and return a parity report."""
    fixture_path = output_dir / "fixture" / "q74_gui_cli_parity.pdf"
    cli_output_dir = output_dir / "cli"
    gui_output_dir = output_dir / "gui"
    report_path = output_dir / PARITY_REPORT
    write_parity_fixture(fixture_path)
    cli_command = [
        sys.executable,
        "-m",
        "pdf2md",
        str(fixture_path),
        "-o",
        str(cli_output_dir),
        "--pages",
        "1",
        "--keep-page-markers",
    ]
    completed = subprocess.run(cli_command, check=False, capture_output=True, text=True)
    gui_summary = None
    if completed.returncode == 0:
        gui_summary = run_gui_conversion(
            GuiConversionRequest(
                input_mode="file",
                input_path=fixture_path,
                output_dir=gui_output_dir,
                options=GuiConversionOptions(pages="1", keep_page_markers=True),
            )
        )
    comparison = (
        compare_artifacts(cli_output_dir, gui_output_dir)
        if completed.returncode == 0 and gui_summary is not None
        else {
            "artifacts": [],
            "summary": {"checked_count": 0, "matched_count": 0, "mismatched_count": 0},
            "passed": False,
        }
    )
    payload = {
        "schema_version": "1.0",
        "kind": "gui_cli_parity_report",
        "local_only": True,
        "status": "passed" if completed.returncode == 0 and gui_summary is not None and comparison["passed"] else "failed",
        "passed": completed.returncode == 0 and gui_summary is not None and comparison["passed"],
        "output_dir": str(output_dir),
        "fixture_label": fixture_path.name,
        "cli": {
            "command": cli_command,
            "exit_code": completed.returncode,
            "stdout_tail": _tail(completed.stdout or ""),
            "stderr_tail": _tail(completed.stderr or ""),
        },
        "gui": {
            "exit_code": gui_summary.exit_code if gui_summary is not None else None,
            "document_count": len(gui_summary.documents) if gui_summary is not None else 0,
        },
        "comparison": comparison,
    }
    write_json(report_path, payload)
    return payload


def _normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json(item) for key, item in sorted(value.items()) if key not in DYNAMIC_JSON_KEYS}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def _tail(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local-only CLI/GUI output parity check.")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = run_parity(args.output_dir)
    print(f"Wrote {args.output_dir / PARITY_REPORT}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
