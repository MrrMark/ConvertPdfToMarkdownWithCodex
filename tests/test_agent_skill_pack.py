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
    assert "--image-mode none" in skill_text
    assert "pdf2md_convert_pdf_windowed" in skill_text
    assert "interrupted_report.json" in skill_text
    assert "figure_ocr_evidence_rag.jsonl" in skill_text
    assert "adapter_metadata" in skill_text
    assert "cross_spec_compatibility" in skill_text


def test_agent_skill_pack_includes_client_adapter_templates() -> None:
    cursor_rule = Path("agent-adapters/cursor/pdf2md-rag-ingest.mdc")
    continue_rule = Path("agent-adapters/continue/pdf2md-rag-ingest.md")
    assert cursor_rule.is_file()
    assert continue_rule.is_file()
    assert "agent-pack/skills/pdf2md-rag-ingest/SKILL.md" in cursor_rule.read_text(encoding="utf-8")
    assert "references/artifacts.md" in cursor_rule.read_text(encoding="utf-8")
    assert "agent-pack/skills/pdf2md-rag-ingest/SKILL.md" in continue_rule.read_text(encoding="utf-8")
    assert "references/artifacts.md" in continue_rule.read_text(encoding="utf-8")
    portability = Path("docs/AGENT_SKILL_PORTABILITY.md").read_text(encoding="utf-8")
    assert "agent-pack/skills/pdf2md-rag-ingest" in portability
    assert "AGENT_SKILL_USAGE_GUIDE.md" in portability
    assert "--overwrite --dry-run" in portability
    assert "Keep Cursor/Continue rules thin" in portability


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
    assert "target <- source" in guide
    assert "--workflow assetless-technical-rag" in guide
    assert "--image-mode none" in guide
    assert "pdf2md_convert_pdf_windowed" in guide
    assert "validate --output-dir output/spec --target all" in guide
    assert "validate_ssd_rag_contract.py" in guide
    assert "page_layout_rag.jsonl" in guide
    assert "figure_ocr_evidence_rag.jsonl" in guide
    assert "adapter_metadata" in guide
    assert "cross_spec_compatibility" in guide
    assert "Do not summarize or rewrite PDF text" in guide


def test_agent_skill_pack_documents_q117_operational_contracts() -> None:
    artifacts = (SKILL_ROOT / "references/artifacts.md").read_text(encoding="utf-8")
    workflows = (SKILL_ROOT / "references/workflows.md").read_text(encoding="utf-8")
    validation = (SKILL_ROOT / "references/validation.md").read_text(encoding="utf-8")
    cursor_rule = Path("agent-adapters/cursor/pdf2md-rag-ingest.mdc").read_text(encoding="utf-8")
    continue_rule = Path("agent-adapters/continue/pdf2md-rag-ingest.md").read_text(encoding="utf-8")

    assert "conversion_state.json" in artifacts
    assert "interrupted_report.json" in artifacts
    assert "page_window_merge_report.json" in artifacts
    assert "pdf2md_plan_page_windows" in workflows
    assert "pdf2md_merge_window_outputs" in workflows
    assert "--image-mode none" in workflows
    assert "summary.interrupted=true" in validation
    assert "--image-mode none" in cursor_rule
    assert "pdf2md_convert_pdf_windowed" in cursor_rule
    assert "--image-mode none" in continue_rule
    assert "pdf2md_convert_pdf_windowed" in continue_rule


def test_agent_skill_pack_documents_latest_sidecar_contracts() -> None:
    skill_text = SKILL_FILE.read_text(encoding="utf-8")
    artifacts = (SKILL_ROOT / "references/artifacts.md").read_text(encoding="utf-8")
    validation = (SKILL_ROOT / "references/validation.md").read_text(encoding="utf-8")

    for sidecar in [
        "page_layout_rag.jsonl",
        "figure_ocr_evidence_rag.jsonl",
        "figure_descriptions_rag.jsonl",
        "figure_structures_rag.jsonl",
    ]:
        assert sidecar in skill_text or sidecar in artifacts
        assert sidecar in artifacts
        assert sidecar in validation

    for field in [
        "adapter_metadata",
        "cross_spec_compatibility",
        "source_sha256",
        "source_dedupe_key",
        "stable_source_id",
        "stable_requirement_seed",
    ]:
        assert field in skill_text or field in artifacts
        assert field in artifacts or field in validation


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
    assert "--rag-profile technical_spec_rag_visual" in completed.stdout
    assert "--domain-adapter nvme" in completed.stdout
    assert "--image-mode placeholder" in completed.stdout


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
    assert "agent-pack/skills/pdf2md-rag-ingest" in completed.stdout
    assert "agent-adapters/cursor/pdf2md-rag-ingest.mdc" in completed.stdout
    assert "agent-adapters/continue/pdf2md-rag-ingest.md" in completed.stdout
    assert "<-" in completed.stdout
