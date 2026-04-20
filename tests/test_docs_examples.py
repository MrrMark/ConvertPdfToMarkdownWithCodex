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
    assert ".\\scripts\\setup_windows_env.bat" in readme
    assert ".\\scripts\\run_batch_folder_windows.bat -InputDir .\\pdfs" in readme


def test_windows_guide_matches_cli_policy() -> None:
    guide = Path("docs/WINDOWS_A_TO_Z_GUIDE.md").read_text(encoding="utf-8")
    assert "python -m pdf2md .\\sample.pdf" in guide
    assert "sample_output\\document.md" in guide
    assert "python -m pdf2md --input-dir .\\pdfs --skip-existing" in guide
    assert "py -3.11 -m venv .venv311" in guide
    assert "py -3.14 -m venv .venv314" in guide
    assert "scripts\\setup_windows_env.ps1" in guide
    assert "scripts\\run_batch_folder_windows.ps1" in guide
    assert ".venv314\\Scripts\\python.exe -m pip install -e .[dev]" in guide
    assert "python -m pdf2md --input-dir .\\pdfs" in guide


def test_windows_script_contracts_are_present() -> None:
    setup_ps1 = Path("scripts/setup_windows_env.ps1")
    setup_bat = Path("scripts/setup_windows_env.bat")
    run_ps1 = Path("scripts/run_batch_folder_windows.ps1")
    run_bat = Path("scripts/run_batch_folder_windows.bat")

    assert setup_ps1.exists()
    assert setup_bat.exists()
    assert run_ps1.exists()
    assert run_bat.exists()

    setup_text = setup_ps1.read_text(encoding="utf-8")
    run_text = run_ps1.read_text(encoding="utf-8")
    setup_bat_text = setup_bat.read_text(encoding="utf-8")
    run_bat_text = run_bat.read_text(encoding="utf-8")

    assert 'py -3.14 -m venv .venv314' in Path("docs/WINDOWS_A_TO_Z_GUIDE.md").read_text(encoding="utf-8")
    assert '"-m", "pip", "install", "-e", ".[dev]"' in setup_text
    assert '"Scripts\\python.exe"' in setup_text
    assert '"-m", "pdf2md"' in run_text
    assert '"--input-dir", $resolvedInputDir' in run_text
    assert "setup_windows_env.ps1" in run_text
    assert "powershell -ExecutionPolicy Bypass -File" in setup_bat_text
    assert "powershell -ExecutionPolicy Bypass -File" in run_bat_text
