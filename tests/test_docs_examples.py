from __future__ import annotations

from pathlib import Path


def test_readme_documents_default_output_and_skip_existing() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "python3 -m pdf2md input.pdf" in readme
    assert "<pdf_stem>_output/" in readme
    assert "python3 -m pdf2md --input-dir ./pdfs --skip-existing" in readme
    assert "python3.11 -m venv .venv311" in readme
    assert "brew install python@3.14" in readme
    assert "./scripts/validate_python_matrix.sh" in readme


def test_windows_guide_matches_cli_policy() -> None:
    guide = Path("docs/WINDOWS_A_TO_Z_GUIDE.md").read_text(encoding="utf-8")
    assert "python -m pdf2md .\\sample.pdf" in guide
    assert "sample_output\\document.md" in guide
    assert "python -m pdf2md --input-dir .\\pdfs --skip-existing" in guide
    assert "py -3.11 -m venv .venv311" in guide
    assert "py -3.14 -m venv .venv314" in guide
