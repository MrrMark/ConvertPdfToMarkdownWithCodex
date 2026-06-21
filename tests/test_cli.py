from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pdf2md.config import default_output_dir_for_input


def _write_large_spec_plan(path: Path, *, domain_adapter: str = "spdm") -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "purpose": "large_spec_preflight_plan",
                "input_pdf": "/tmp/security.pdf",
                "source_sha256": "1" * 64,
                "total_pages": 250,
                "selected_page_count": 250,
                "sampled_pages": [1, 125, 250],
                "recommendation": {
                    "preferred_mcp_tool": "pdf2md_convert_pdf",
                    "recommended_options": {
                        "rag_profile": "technical_spec_rag",
                        "domain_adapter": domain_adapter,
                        "image_mode": "none",
                        "rag_sidecar_scope": "minimal",
                        "page_workers": 2,
                        "image_extraction_page_timeout_seconds": None,
                        "image_extraction_stage_timeout_seconds": 120,
                        "figure_semantics_stage_timeout_seconds": 60,
                    },
                    "recommended_option_sources": {
                        "domain_adapter": "domain_adapter_recommendation",
                    },
                    "domain_adapter_recommendation": {
                        "recommended_domain_adapter": domain_adapter,
                        "confidence": "high",
                        "recommendation_basis": {"ambiguous": False},
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


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
    assert (output_dir / "text_blocks_rag.jsonl").exists()
    assert (output_dir / "semantic_units_rag.jsonl").exists()
    assert (output_dir / "requirements_rag.jsonl").exists()
    assert (output_dir / "cross_refs_rag.jsonl").exists()
    assert (output_dir / "requirement_traceability_rag.jsonl").exists()
    assert (output_dir / "technical_tables_rag.jsonl").exists()
    assert (output_dir / "retrieval_chunks_rag.jsonl").exists()
    assert (output_dir / "figures_rag.jsonl").exists()
    first_chunk = json.loads((output_dir / "retrieval_chunks_rag.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first_chunk["schema_version"] == "1.0"
    assert len(first_chunk["source_sha256"]) == 64


def test_cli_rag_profile_applies_purpose_specific_option_bundle(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-profile"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--rag-profile",
        "confidential_rag",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_profile"] == "confidential_rag"
    assert manifest["options"]["confidential_safe_mode"] is True
    assert manifest["options"]["rag_table_output"] == "jsonl"
    assert manifest["options"]["retrieval_tokenizer"] == "regex"
    assert manifest["options"]["rag_contextual_embedding_text"] is True
    assert manifest["options"]["rag_merge_sibling_text_chunks"] is True
    assert manifest["options"]["rag_chunk_relationship_metadata"] is True
    assert (output_dir / "sanitized_report.json").exists()


def test_cli_technical_spec_profile_without_domain_adapter_emits_advisory(
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "cli-technical-missing-domain"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--rag-profile",
        "technical_spec_rag",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_profile"] == "technical_spec_rag"
    assert manifest["options"]["domain_adapter"] == "none"
    assert report["status"] == "success"
    assert report["warnings"][0]["code"] == "TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING"
    assert report["warnings"][0]["details"]["recommended_domain_adapters"] == [
        "nvme",
        "pcie",
        "ocp",
        "tcg",
        "spdm",
        "caliptra",
        "customer-requirements",
        "manual",
    ]
    assert report["summary"]["technical_profile_domain_adapter_missing"] is True
    assert report["summary"]["actionable_warning_count"] == 0
    assert report["summary"]["advisory_warning_count"] == 1


def test_cli_visual_technical_spec_profile_enables_visual_sidecars(
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "cli-technical-visual"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--rag-profile",
        "technical_spec_rag_visual",
        "--domain-adapter",
        "nvme",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_profile"] == "technical_spec_rag_visual"
    assert manifest["options"]["image_mode"] == "referenced"
    assert manifest["options"]["rag_figure_text_chunks"] is True
    assert manifest["options"]["figure_region_ocr"] is True
    assert manifest["options"]["rag_generated_figure_descriptions"] is True
    assert manifest["options"]["figure_structure_extraction"] is True
    assert (output_dir / "figure_descriptions_rag.jsonl").exists()
    assert (output_dir / "figure_structures_rag.jsonl").exists()
    assert report["summary"]["rag_figure_text_chunks"] is True
    assert report["summary"]["figure_region_ocr"] is True
    assert report["summary"]["rag_generated_figure_descriptions"] is True
    assert report["summary"]["figure_structure_extraction"] is True


def test_cli_technical_spec_profile_strict_mode_requires_domain_adapter(
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "cli-technical-strict-missing-domain"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--rag-profile",
        "technical_spec_rag",
        "--require-domain-adapter-for-technical-profile",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 2
    assert "technical spec RAG profiles require --domain-adapter" in completed.stderr


def test_cli_apply_plan_maps_preflight_options_and_writes_audit(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-apply-plan"
    plan_path = tmp_path / "large-spec-plan.json"
    _write_large_spec_plan(plan_path)
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--apply-plan",
        str(plan_path),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((output_dir / "plan_apply_report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_profile"] == "technical_spec_rag"
    assert manifest["options"]["domain_adapter"] == "spdm"
    assert manifest["options"]["image_mode"] == "none"
    assert manifest["options"]["rag_sidecar_scope"] == "minimal"
    assert audit["purpose"] == "large_spec_plan_apply_audit"
    assert audit["raw_content_included"] is False
    assert audit["applied_options"]["page_workers"] == 2
    assert audit["option_matrix"]["before"]["rag_profile"] == "preserve"
    assert audit["option_matrix"]["after"]["domain_adapter"] == "spdm"
    assert "sample_text" not in json.dumps(audit, ensure_ascii=False, sort_keys=True)


def test_cli_apply_plan_keeps_explicit_option_precedence(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-apply-plan-explicit"
    plan_path = tmp_path / "large-spec-plan.json"
    _write_large_spec_plan(plan_path, domain_adapter="spdm")
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--apply-plan",
        str(plan_path),
        "--domain-adapter",
        "tcg",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((output_dir / "plan_apply_report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_profile"] == "technical_spec_rag"
    assert manifest["options"]["domain_adapter"] == "tcg"
    assert audit["option_matrix"]["before"]["domain_adapter"] == "tcg"
    assert audit["option_matrix"]["after"]["domain_adapter"] == "tcg"
    assert {
        "option": "domain_adapter",
        "reason": "explicit_option_precedence",
        "value": "spdm",
    } in audit["skipped_options"]


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


def test_cli_accepts_rag_table_output_mode(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-rag-table-output"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--rag-table-output",
        "markdown",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_table_output"] == "markdown"
    assert report["summary"]["rag_table_output"] == "markdown"
    assert (output_dir / "rag_tables.md").exists()
    assert not (output_dir / "tables_rag.jsonl").exists()


def test_cli_accepts_fast_output_profile(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-fast-profile"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--output-profile",
        "fast",
        "--rag-table-output",
        "jsonl",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["output_profile"] == "fast"
    assert manifest["options"]["rag_sidecar_scope"] == "none"
    assert report["summary"]["rag_sidecar_scope"] == "none"
    assert not (output_dir / "tables_rag.jsonl").exists()
    assert not (output_dir / "retrieval_chunks_rag.jsonl").exists()


def test_cli_accepts_rag_figure_text_chunks_option(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-figure-text"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--image-mode",
        "placeholder",
        "--rag-figure-text-chunks",
        "--figure-region-ocr",
        "--rag-generated-figure-descriptions",
        "--figure-description-backend",
        "docling",
        "--figure-structure-extraction",
        "--image-extraction-page-timeout-seconds",
        "10",
        "--image-extraction-stage-timeout-seconds",
        "20",
        "--figure-semantics-stage-timeout-seconds",
        "30",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["image_mode"] == "placeholder"
    assert manifest["options"]["rag_figure_text_chunks"] is True
    assert manifest["options"]["figure_region_ocr"] is True
    assert manifest["options"]["rag_generated_figure_descriptions"] is True
    assert manifest["options"]["figure_description_backend"] == "docling"
    assert manifest["options"]["figure_structure_extraction"] is True
    assert manifest["options"]["image_extraction_page_timeout_seconds"] == 10.0
    assert manifest["options"]["image_extraction_stage_timeout_seconds"] == 20.0
    assert manifest["options"]["figure_semantics_stage_timeout_seconds"] == 30.0
    assert (output_dir / "figure_descriptions_rag.jsonl").exists()
    assert (output_dir / "figure_structures_rag.jsonl").exists()
    assert report["summary"]["rag_figure_text_chunks"] is True
    assert report["summary"]["figure_text_chunk_record_count"] == 0
    assert report["summary"]["figure_region_ocr"] is True
    assert report["summary"]["figure_region_ocr_attempted_count"] == 0
    assert report["summary"]["figure_description_backend"] == "docling"
    assert report["summary"]["figure_description_record_count"] == 0
    assert report["summary"]["figure_structure_record_count"] == 0
    assert report["summary"]["image_extraction_page_timeout_seconds"] == 10.0
    assert report["summary"]["image_extraction_stage_timeout_seconds"] == 20.0
    assert report["summary"]["figure_semantics_stage_timeout_seconds"] == 30.0


def test_cli_accepts_domain_adapter_option(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-domain-adapter"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--rag-profile",
        "technical_spec_rag",
        "--domain-adapter",
        "nvme",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_profile"] == "technical_spec_rag"
    assert manifest["options"]["domain_adapter"] == "nvme"
    assert manifest["options"]["domain_units_jsonl_filename"] == "domain_units_rag.jsonl"
    assert report["summary"]["domain_unit_file_count"] == 1
    assert report["summary"]["technical_profile_domain_adapter_missing"] is False
    assert (output_dir / "domain_units_rag.jsonl").exists()


def test_cli_accepts_manual_domain_adapter_inputs(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-manual-domain-adapter"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--rag-profile",
        "technical_spec_rag",
        "--domain-adapter",
        "manual",
        "--manual-domain-adapter-label",
        "Customer A Requirements",
        "--manual-domain-adapter-keywords",
        "Customer Key, Customer Requirement",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_profile"] == "technical_spec_rag"
    assert manifest["options"]["domain_adapter"] == "manual"
    assert manifest["options"]["manual_domain_adapter_label"] == "Customer A Requirements"
    assert manifest["options"]["manual_domain_adapter_keywords"] == "Customer Key, Customer Requirement"
    assert report["summary"]["manual_domain_adapter_label"] == "Customer A Requirements"
    assert report["summary"]["manual_domain_adapter_keywords"] == "Customer Key, Customer Requirement"
    assert (output_dir / "domain_units_rag.jsonl").exists()


def test_cli_accepts_quality_options(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-out-quality-options"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--remove-header-footer",
        "--dedupe-images",
        "--repair-hyphenation",
        "--figure-crop-fallback",
        "--ocr-lang",
        "kor+eng",
        "--ocr-backend",
        "tesseract",
        "--debug",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["options"]["remove_header_footer"] is True
    assert manifest["options"]["dedupe_images"] is True
    assert manifest["options"]["repair_hyphenation"] is True
    assert manifest["options"]["figure_crop_fallback"] is True
    assert manifest["options"]["ocr_lang"] == "kor+eng"
    assert manifest["options"]["ocr_backend"] == "tesseract"
    assert manifest["options"]["rag_text_blocks_output"] == "jsonl"
    assert manifest["options"]["rag_text_blocks_jsonl_filename"] == "text_blocks_rag.jsonl"
    assert manifest["options"]["semantic_layer_output"] == "jsonl"
    assert manifest["options"]["semantic_units_jsonl_filename"] == "semantic_units_rag.jsonl"
    assert manifest["options"]["requirements_jsonl_filename"] == "requirements_rag.jsonl"
    assert manifest["options"]["cross_refs_jsonl_filename"] == "cross_refs_rag.jsonl"
    assert manifest["options"]["requirement_traceability_jsonl_filename"] == "requirement_traceability_rag.jsonl"
    assert manifest["options"]["technical_tables_jsonl_filename"] == "technical_tables_rag.jsonl"
    assert manifest["options"]["retrieval_chunks_output"] == "jsonl"
    assert manifest["options"]["retrieval_chunks_jsonl_filename"] == "retrieval_chunks_rag.jsonl"
    assert manifest["options"]["figures_rag_output"] == "jsonl"
    assert manifest["options"]["figures_rag_jsonl_filename"] == "figures_rag.jsonl"
    assert manifest["options"]["domain_adapter"] == "none"
    assert manifest["options"]["domain_units_jsonl_filename"] == "domain_units_rag.jsonl"
    assert manifest["options"]["confidential_safe_mode"] is False
    assert (output_dir / "debug" / "page-0001-raw-lines.json").exists()


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
    assert (output_root / "alpha" / "assets" / "images").exists()
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
    assert alpha_entry["files"]["text_blocks_rag"].endswith("alpha/text_blocks_rag.jsonl")
    assert alpha_entry["files"]["semantic_units_rag"].endswith("alpha/semantic_units_rag.jsonl")
    assert alpha_entry["files"]["requirements_rag"].endswith("alpha/requirements_rag.jsonl")
    assert alpha_entry["files"]["cross_refs_rag"].endswith("alpha/cross_refs_rag.jsonl")
    assert alpha_entry["files"]["requirement_traceability_rag"].endswith(
        "alpha/requirement_traceability_rag.jsonl"
    )
    assert alpha_entry["files"]["technical_tables_rag"].endswith("alpha/technical_tables_rag.jsonl")
    assert alpha_entry["files"]["retrieval_chunks_rag"].endswith("alpha/retrieval_chunks_rag.jsonl")
    assert alpha_entry["files"]["figures_rag"].endswith("alpha/figures_rag.jsonl")
    corpus_manifest = json.loads((output_root / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert corpus_manifest["schema_version"] == "1.0"
    assert corpus_manifest["purpose"] == "rag_corpus_ingest"
    assert [item["doc_id"] for item in corpus_manifest["documents"]] == ["alpha", "beta"]
    corpus_alpha = next(item for item in corpus_manifest["documents"] if item["doc_id"] == "alpha")
    assert len(corpus_alpha["source_sha256"]) == 64
    assert corpus_alpha["selected_pages"] == [1, 2]
    assert corpus_alpha["files"]["retrieval_chunks_rag"].endswith("alpha/retrieval_chunks_rag.jsonl")
    assert corpus_alpha["files"]["figures_rag"].endswith("alpha/figures_rag.jsonl")


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
    corpus_manifest = json.loads((output_root / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert corpus_manifest["documents"][0]["doc_id"] == "alpha"
    assert corpus_manifest["documents"][0]["skipped"] is True


def test_cli_confidential_safe_mode_redacts_public_metadata(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "safe-out"
    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        str(sample_pdf),
        "-o",
        str(output_dir),
        "--pages",
        "1",
        "--confidential-safe-mode",
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["input_file"] == "redacted.pdf"
    assert manifest["options"]["confidential_safe_mode"] is True
    assert manifest["options"]["external_llm_calls"] is False
    assert report["summary"]["confidential_safe_mode"] is True
    assert (output_dir / "sanitized_report.json").exists()


def test_cli_batch_mode_writes_incremental_corpus_diff(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "batch-input-diff"
    input_dir.mkdir()
    (input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())
    previous_manifest = tmp_path / "previous_corpus_manifest.json"
    previous_manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "purpose": "rag_corpus_ingest",
                "input_dir": str(input_dir),
                "output_dir": str(input_dir / "output"),
                "documents": [
                    {
                        "doc_id": "alpha",
                        "input_pdf": str(input_dir / "alpha.pdf"),
                        "source_sha256": "0" * 64,
                        "output_dir": str(input_dir / "output" / "alpha"),
                        "status": "success",
                        "selected_pages": [1],
                        "skipped": False,
                        "files": {},
                    },
                    {
                        "doc_id": "removed",
                        "input_pdf": str(input_dir / "removed.pdf"),
                        "source_sha256": "1" * 64,
                        "output_dir": str(input_dir / "output" / "removed"),
                        "status": "success",
                        "selected_pages": [1],
                        "skipped": False,
                        "files": {},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "-m",
        "pdf2md",
        "--input-dir",
        str(input_dir),
        "--previous-corpus-manifest",
        str(previous_manifest),
    ]

    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    diff = json.loads((input_dir / "output" / "corpus_diff_report.json").read_text(encoding="utf-8"))
    assert diff["summary"]["changed_count"] == 1
    assert diff["summary"]["removed_count"] == 1
    assert [entry["status"] for entry in diff["entries"]] == ["changed", "removed"]
    impact = json.loads((input_dir / "output" / "requirement_change_impact_report.json").read_text(encoding="utf-8"))
    assert impact["purpose"] == "rag_requirement_change_impact"


def test_cli_batch_mode_reuses_unchanged_previous_outputs(sample_pdf: Path, tmp_path: Path) -> None:
    previous_input_dir = tmp_path / "previous-batch"
    current_input_dir = tmp_path / "current-batch"
    previous_input_dir.mkdir()
    current_input_dir.mkdir()
    (previous_input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())
    (current_input_dir / "alpha.pdf").write_bytes(sample_pdf.read_bytes())

    first_run = subprocess.run(
        [sys.executable, "-m", "pdf2md", "--input-dir", str(previous_input_dir), "--pages", "1"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first_run.returncode == 0
    previous_manifest = previous_input_dir / "output" / "corpus_manifest.json"

    second_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf2md",
            "--input-dir",
            str(current_input_dir),
            "--pages",
            "1",
            "--previous-corpus-manifest",
            str(previous_manifest),
            "--reuse-unchanged",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert second_run.returncode == 0
    output_root = current_input_dir / "output"
    assert (output_root / "alpha" / "alpha.md").exists()
    batch_report = json.loads((output_root / "batch_report.json").read_text(encoding="utf-8"))
    assert batch_report["summary"]["skipped_count"] == 1
    assert batch_report["documents"][0]["status"] == "skipped"
    diff = json.loads((output_root / "corpus_diff_report.json").read_text(encoding="utf-8"))
    assert diff["summary"]["unchanged_count"] == 1
    corpus_manifest = json.loads((output_root / "corpus_manifest.json").read_text(encoding="utf-8"))
    assert corpus_manifest["documents"][0]["skipped"] is True


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
