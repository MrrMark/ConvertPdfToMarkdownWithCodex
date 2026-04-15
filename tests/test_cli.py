from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from pathlib import Path


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
    assert batch_report["summary"]["total_documents"] == 2
    assert batch_report["summary"]["success_count"] == 1
    assert batch_report["summary"]["failed_count"] == 1
    alpha_entry = next(item for item in batch_report["documents"] if Path(item["input_pdf"]).name == "alpha.pdf")
    beta_entry = next(item for item in batch_report["documents"] if Path(item["input_pdf"]).name == "beta.pdf")
    assert alpha_entry["files"]["markdown"].endswith("alpha/alpha.md")
    assert beta_entry["status"] == "failed"


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
