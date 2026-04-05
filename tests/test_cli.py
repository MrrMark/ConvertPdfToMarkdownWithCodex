from __future__ import annotations

import json
import subprocess
import sys
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
