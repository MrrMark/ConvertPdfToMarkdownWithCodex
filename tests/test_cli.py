from __future__ import annotations

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
