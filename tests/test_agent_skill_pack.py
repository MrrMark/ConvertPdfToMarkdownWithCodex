from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path("agent-pack/skills/pdf2md-rag-ingest")
SKILL_FILE = SKILL_ROOT / "SKILL.md"


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    raw = text.split("---", 2)[1]
    values: dict[str, str] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith(" ") and current_key is not None:
            values[current_key] = f"{values[current_key]} {line.strip()}"
            continue
        key, _, value = line.partition(":")
        values[key.strip()] = value.strip()
        current_key = key.strip()
    return values


def test_agent_skill_pack_has_valid_agent_skill_frontmatter() -> None:
    frontmatter = _frontmatter(SKILL_FILE)

    assert frontmatter["name"] == "pdf2md-rag-ingest"
    assert SKILL_ROOT.name == frontmatter["name"]
    assert 1 <= len(frontmatter["description"]) <= 1024
    assert "Convert PDF files" in frontmatter["description"]
    assert "compatibility" in frontmatter


def test_agent_skill_pack_references_exist_and_stay_linked() -> None:
    skill_text = SKILL_FILE.read_text(encoding="utf-8")
    references = [
        "references/workflows.md",
        "references/artifacts.md",
        "references/validation.md",
        "references/adapters.md",
    ]

    for reference in references:
        assert reference in skill_text
        assert (SKILL_ROOT / reference).is_file()


def test_agent_skill_pack_includes_client_adapter_templates() -> None:
    assert (Path("agent-adapters/cursor/pdf2md-rag-ingest.mdc")).is_file()
    assert (Path("agent-adapters/continue/pdf2md-rag-ingest.md")).is_file()
    portability = Path("docs/AGENT_SKILL_PORTABILITY.md").read_text(encoding="utf-8")
    assert "agent-pack/skills/pdf2md-rag-ingest" in portability
    assert "AGENT_SKILL_USAGE_GUIDE.md" in portability


def test_agent_skill_usage_guide_documents_common_client_operations() -> None:
    guide = Path("docs/AGENT_SKILL_USAGE_GUIDE.md").read_text(encoding="utf-8")

    assert "Claude Code, Cline, Roo Code, Cursor, Continue" in guide
    assert "agent-pack/skills/pdf2md-rag-ingest/" in guide
    assert ".agents/skills/pdf2md-rag-ingest/" in guide
    assert ".claude/skills/pdf2md-rag-ingest/" in guide
    assert ".cline/skills/pdf2md-rag-ingest/" in guide
    assert ".roo/skills/pdf2md-rag-ingest/" in guide
    assert ".cursor/rules/pdf2md-rag-ingest.mdc" in guide
    assert ".continue/rules/pdf2md-rag-ingest.md" in guide
    assert "--clients all --scope project --mode copy --dry-run" in guide
    assert "--overwrite" in guide
    assert "py -3.14 scripts\\install_agent_skill_pack.py" in guide
    assert "symlink" in guide
    assert "--workflow assetless-technical-rag" in guide
    assert "validate --output-dir output/spec --target all" in guide
    assert "Do not summarize or rewrite PDF text" in guide


def test_pdf2md_agent_runner_dry_run_builds_assetless_command() -> None:
    runner = SKILL_ROOT / "scripts" / "pdf2md_agent_runner.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--project-root",
            ".",
            "convert",
            "spec.pdf",
            "--workflow",
            "assetless-technical-rag",
            "--domain-adapter",
            "nvme",
            "--output-dir",
            "output/spec",
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--rag-profile technical_spec_rag" in completed.stdout
    assert "--domain-adapter nvme" in completed.stdout
    assert "--image-mode placeholder --rag-figure-text-chunks" in completed.stdout


def test_install_agent_skill_pack_dry_run_lists_all_clients() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/install_agent_skill_pack.py",
            "--project-root",
            ".",
            "--clients",
            "all",
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert ".agents/skills/pdf2md-rag-ingest" in completed.stdout
    assert ".claude/skills/pdf2md-rag-ingest" in completed.stdout
    assert ".cline/skills/pdf2md-rag-ingest" in completed.stdout
    assert ".roo/skills/pdf2md-rag-ingest" in completed.stdout
    assert ".cursor/rules/pdf2md-rag-ingest.mdc" in completed.stdout
    assert ".continue/rules/pdf2md-rag-ingest.md" in completed.stdout
