from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pdf2md.config import default_output_dir_for_input


def test_cli_runs_and_writes_outputs(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--keep-page-markers",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    assert (output_dir / "document.md").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "report.json").exists()


def test_cli_uses_default_output_dir_when_output_dir_is_omitted(sample_pdf: Path) -> None:
    default_output_dir = default_output_dir_for_input(sample_pdf)
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "--pages",
        "1",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    assert (default_output_dir / "document.md").exists()
    assert (default_output_dir / "manifest.json").exists()
    assert (default_output_dir / "report.json").exists()


def test_cli_no_page_markers(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-no-markers"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--no-page-markers",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert completed.returncode == 0
    content = (output_dir / "document.md").read_text(encoding="utf-8")
    assert "<!-- page:" not in content


def test_cli_invalid_page_range_returns_fatal(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-invalid-pages"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "99",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 1
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["warnings"][0]["code"] == "INVALID_PAGE_RANGE"


def test_cli_encrypted_pdf_requires_password(encrypted_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-encrypted"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(encrypted_pdf),
        "-o",
        str(output_dir),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 1
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["warnings"][0]["code"] == "PDF_OPEN_FAILED"


def test_cli_encrypted_pdf_with_password_succeeds(encrypted_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-encrypted-ok"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(encrypted_pdf),
        "-o",
        str(output_dir),
        "--password",
        "secret",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    assert (output_dir / "document.md").exists()


def test_cli_accepts_html_table_mode(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-html-mode"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--table-mode",
        "html",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["options"]["table_mode"] == "html"


def test_cli_accepts_markdown_table_mode(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-markdown-mode"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--table-mode",
        "markdown",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["options"]["table_mode"] == "markdown"


def test_cli_batch_mode_generates_per_pdf_outputs(
    sample_pdf: Path,
    encrypted_pdf: Path,
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "batch-input"
    input_dir.mkdir()
    first_pdf = input_dir / "alpha.pdf"
    second_pdf = input_dir / "beta.pdf"
    first_pdf.write_bytes(sample_pdf.read_bytes())
    second_pdf.write_bytes(encrypted_pdf.read_bytes())

    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        "--input-dir",
        str(input_dir),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 2
    output_root = input_dir / "output"
    assert (output_root / "alpha" / "alpha.md").exists()
    assert (output_root / "alpha" / "alpha_manifest.json").exists()
    assert (output_root / "alpha" / "alpha_report.json").exists()
    assert (output_root / "alpha" / "alpha_assets" / "images").exists()
    assert (output_root / "beta" / "beta_report.json").exists()
    batch_report = json.loads((output_root / "batch_report.json").read_text(encoding="utf-8"))
    assert batch_report["schema_version"] == "1.0"
    assert batch_report["summary"]["total_documents"] == 2
    assert batch_report["summary"]["success_count"] == 1
    assert batch_report["summary"]["failed_count"] == 1
    assert batch_report["summary"]["skipped_count"] == 0
    alpha_entry = next(item for item in batch_report["documents"] if Path(item["input_pdf"]).name == "alpha.pdf")
    beta_entry = next(item for item in batch_report["documents"] if Path(item["input_pdf"]).name == "beta.pdf")
    assert alpha_entry["files"]["markdown"].endswith("alpha/alpha.md")
    assert beta_entry["status"] == "failed"
    assert alpha_entry["duration_ms"] >= 0
    assert isinstance(alpha_entry["warning_count"], int)
    assert isinstance(alpha_entry["table_count"], int)
    assert isinstance(alpha_entry["image_count"], int)
    assert isinstance(alpha_entry["used_ocr"], bool)


def test_cli_batch_mode_skip_existing_marks_document_skipped(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "batch-input-skip"
    input_dir.mkdir()
    (input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())
    output_root = input_dir / "output"
    document_output_dir = output_root / "alpha"
    document_output_dir.mkdir(parents=True)
    (document_output_dir / "alpha.md").write_text("existing markdown\n", encoding="utf-8")
    (document_output_dir / "alpha_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "input_file": "alpha.pdf",
                "total_pages": 1,
                "selected_pages": [1],
                "options": {},
                "images": [],
                "excluded_images": [],
                "tables": [],
                "ocr_pages": [],
                "warnings": [],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (document_output_dir / "alpha_report.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "started_at": "2024-01-02T03:04:05Z",
                "finished_at": "2024-01-02T03:04:05Z",
                "duration_ms": 0,
                "status": "success",
                "engine_usage": {"pypdf": True, "pdfplumber": True, "ocr": False, "tables": False, "images": False},
                "failed_pages": [],
                "warnings": [],
                "page_results": [],
                "summary": {
                    "processed_pages": 0,
                    "warning_count": 0,
                    "failed_page_count": 0,
                    "partial_success": False,
                    "ocr_confidence_by_page": {},
                    "excluded_image_count": 0,
                    "excluded_images": [],
                    "total_deduplicated_blocks": 0,
                    "total_suppressed_lines": 0,
                    "deduplicated_blocks": [],
                    "suppressed_lines": [],
                    "table_quality": [],
                    "table_fallback_count": 0,
                    "table_fallbacks": [],
                    "table_mode_requested": "auto",
                    "table_total": 0,
                    "table_html_count": 0,
                    "table_gfm_count": 0,
                    "table_recovered_count": 0,
                    "table_unresolved_count": 0,
                    "table_markdown_forced_count": 0,
                    "table_html_forced_count": 0,
                    "low_confidence_pages": [],
                    "page_status_counts": {"success": 0, "partial_success": 0, "failed": 0},
                    "structure_marker_suppressed_count": 0,
                    "structure_marker_recovered_count": 0,
                    "structure_marker_recovered_exact_count": 0,
                    "structure_marker_recovered_context_count": 0,
                    "structure_marker_suppressed_no_candidate_count": 0,
                    "structure_marker_suppressed_ambiguous_count": 0,
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        "--input-dir",
        str(input_dir),
        "--skip-existing",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    assert (document_output_dir / "alpha.md").read_text(encoding="utf-8") == "existing markdown\n"
    batch_report = json.loads((output_root / "batch_report.json").read_text(encoding="utf-8"))
    assert batch_report["summary"]["skipped_count"] == 1
    assert batch_report["documents"][0]["status"] == "skipped"
    assert batch_report["documents"][0]["skipped"] is True


def test_cli_batch_mode_rejects_output_dir(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "batch-input"
    input_dir.mkdir()
    (input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())

    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        "--input-dir",
        str(input_dir),
        "-o",
        str(tmp_path / "unused"),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 2
    assert "--output-dir is not supported" in completed.stderr


def test_cli_batch_mode_requires_pdfs(tmp_path: Path) -> None:
    input_dir = tmp_path / "empty-input"
    input_dir.mkdir()

    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        "--input-dir",
        str(input_dir),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 2
    assert "No PDF files found in directory" in completed.stderr


def test_cli_rejects_single_and_batch_inputs_together(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "batch-input"
    input_dir.mkdir()
    (input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())

    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "--input-dir",
        str(input_dir),
        "-o",
        str(tmp_path / "out"),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 2
    assert "Use either input_pdf or --input-dir" in completed.stderr
