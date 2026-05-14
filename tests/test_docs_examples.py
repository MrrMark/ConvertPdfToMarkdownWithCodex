from __future__ import annotations

from pathlib import Path


def test_readme_documents_default_output_and_skip_existing() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "python3 -m pdf2md input.pdf" in readme
    assert "<pdf_stem>_output/" in readme
    assert "python3 -m pdf2md --input-dir ./pdfs --skip-existing" in readme
    assert "python3 -m pdf2md input.pdf -o output/ --password secret" in readme
    assert "python3.11 -m venv .venv311" in readme
    assert "brew install python@3.14" in readme
    assert "./scripts/validate_python_matrix.sh" in readme
    assert ".\\scripts\\setup_windows_env.bat" in readme
    assert ".\\scripts\\run_batch_folder_windows.bat -InputDir .\\pdfs" in readme
    assert '문서별 상태: `success`, `partial_success`, `failed`, `skipped`' in readme
    assert 'status == "skipped"' in readme
    assert "summary.page_cache_hits" in readme
    assert "summary.text_line_extract_count" in readme
    assert "text_blocks_rag.jsonl" in readme
    assert "semantic_units_rag.jsonl" in readme
    assert "requirements_rag.jsonl" in readme
    assert "cross_refs_rag.jsonl" in readme
    assert "requirement_traceability_rag.jsonl" in readme
    assert "technical_tables_rag.jsonl" in readme
    assert "summary.rag_text_block_record_count" in readme
    assert "summary.semantic_unit_record_count" in readme
    assert "summary.normative_requirement_count" in readme
    assert "summary.technical_table_record_count" in readme
    assert "--confidential-safe-mode" in readme
    assert "rag_header_strategy" in readme
    assert "scripts/run_corpus_eval.py" in readme
    assert "scripts/benchmark_conversion.py" in readme
    assert "scripts/check_ocr_runtime.py --ocr-lang kor+eng" in readme
    assert "scripts/run_release_gates.py" in readme
    assert "scripts/run_ssd_corpus_profile.py" in readme
    assert "scripts/validate_ssd_rag_contract.py" in readme
    assert "rag_requirements.py" in readme
    assert "rag_technical_tables.py" in readme
    assert "requirement_change_impact_report.json" in readme
    assert "--ssd-agent-spec-type TCG" in readme
    assert "release_gate_report.json" in readme
    assert "--baseline-report pdf/baseline/corpus_eval_report.json" in readme
    assert "--max-duration-regression 0.2" in readme
    assert "docs/OUTPUT_SCHEMA.md" in readme
    assert "docs/schema/manifest.schema.json" in readme
    assert "scripts/export_output_schema.py --check" in readme
    assert "python -m build" in readme
    assert "benchmark_report.json" in readme
    assert "docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md" in readme
    assert "pdf/v10" not in readme
    assert "프로젝트 scaffold 생성" not in readme
    assert "metadata.py" not in readme
    assert "html_table.py" not in readme


def test_windows_guide_matches_cli_policy() -> None:
    guide = Path("docs/WINDOWS_A_TO_Z_GUIDE.md").read_text(encoding="utf-8")
    assert "python -m pdf2md .\\sample.pdf" in guide
    assert "sample_output\\document.md" in guide
    assert "python -m pdf2md --input-dir .\\pdfs --skip-existing" in guide
    assert "python -m pdf2md .\\sample.pdf -o .\\output --password secret" in guide
    assert "py -3.11 -m venv .venv311" in guide
    assert "py -3.14 -m venv .venv314" in guide
    assert "scripts\\setup_windows_env.ps1" in guide
    assert "scripts\\run_batch_folder_windows.ps1" in guide
    assert ".venv314\\Scripts\\python.exe -m pip install -e .[dev]" in guide
    assert "python -m pdf2md --input-dir .\\pdfs" in guide
    assert "ZIP 배포본 + 원클릭 스크립트 경로에서는 필수가 아님" in guide
    assert "status == \"skipped\"" in guide
    assert "summary.page_cache_hits" in guide
    assert "summary.text_line_extract_count" in guide
    assert "text_blocks_rag.jsonl" in guide
    assert "semantic_units_rag.jsonl" in guide
    assert "requirements_rag.jsonl" in guide
    assert "cross_refs_rag.jsonl" in guide
    assert "requirement_traceability_rag.jsonl" in guide
    assert "technical_tables_rag.jsonl" in guide
    assert "summary.rag_text_block_record_count" in guide
    assert "summary.semantic_unit_record_count" in guide
    assert "summary.normative_requirement_count" in guide
    assert "summary.technical_table_record_count" in guide
    assert "--confidential-safe-mode" in guide
    assert "rag_header_strategy" in guide
    assert "scripts\\run_corpus_eval.py" in guide
    assert "scripts\\benchmark_conversion.py" in guide
    assert "scripts\\check_ocr_runtime.py --ocr-lang kor+eng" in guide
    assert "scripts\\run_release_gates.py" in guide
    assert "scripts\\run_ssd_corpus_profile.py" in guide
    assert "scripts\\validate_ssd_rag_contract.py" in guide
    assert "requirement_change_impact_report.json" in guide
    assert "--ssd-agent-spec-type TCG" in guide
    assert "release_gate_report.json" in guide
    assert "--baseline-report pdf\\baseline\\corpus_eval_report.json" in guide
    assert "--max-duration-regression 0.2" in guide
    assert "docs\\OUTPUT_SCHEMA.md" in guide
    assert "docs\\schema\\manifest.schema.json" in guide
    assert "scripts\\export_output_schema.py --check" in guide
    assert "python -m build" in guide
    assert "benchmark_report.json" in guide
    assert "docs\\NEXT_QUALITY_IMPROVEMENT_PLAN.md" in guide
    assert "- Git\n  - `git clone`, `git pull` 같은 저장소 동기화 흐름에서만 필요" in guide


def test_ci_and_next_plan_contracts_are_present() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    next_plan = Path("docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md").read_text(encoding="utf-8")
    output_schema = Path("docs/OUTPUT_SCHEMA.md").read_text(encoding="utf-8")
    quality_scorecard = Path("docs/QUALITY_SCORECARD.md").read_text(encoding="utf-8")

    assert "python-version" in workflow
    assert '"3.11"' in workflow
    assert "python -m pytest" in workflow
    assert "python -m pdf2md --help" in workflow
    assert "앞으로 작업할 항목만" in next_plan
    assert "작업이 완료되고 테스트 통과 및 PR merge까지 끝나면" in next_plan
    assert "구현 완료, 테스트 통과, PR merge까지 끝난 항목은" in next_plan
    assert "Q02. Font/Geometry 기반 텍스트 블록 구조화" not in next_plan
    assert "Q03. Figure Crop Fallback 시각 검증 및 보정" not in next_plan
    assert "Q04. Multi-page Table Continuation 보정" not in next_plan
    assert "Q08. Release Gate Runner 통합" not in next_plan
    assert "Q09. Machine-readable Output Schema Export" not in next_plan
    assert "Q10. RAG 운영용 스펙 Semantic Layer" not in next_plan
    assert "Q11. RAG Retrieval Chunk Pack" not in next_plan
    assert "Q15. Domain Adapter" not in next_plan
    assert "Q16. Domain-Specific Technical Spec Adapter Framework" not in next_plan
    assert "Q22. Confidential Corpus Safe Mode" not in next_plan
    assert "Q25. Domain Adapter Coverage Expansion" not in next_plan
    assert "Q26. Real Technical Corpus Calibration Gate" not in next_plan
    assert "Q30. Diagram OCR And Label Recovery Calibration" not in next_plan
    assert "Q31. Local Corpus Profile Runner" not in next_plan
    assert "Q32. Requirement Impact Review Pack" not in next_plan
    assert "Q33. Technical Cross-Reference Resolver Hardening" not in next_plan
    assert "Q34. Offline Index Contract Validator" not in next_plan
    assert "Q35. Rendered Diagram Fixture Suite" in next_plan
    assert "Q36. Page-Level Parallel Extractor" in next_plan
    assert "현재 남은 작업 없음." not in next_plan
    assert "Q01. 실문서 Corpus 품질 게이트 고도화" not in next_plan
    assert "Q05. OCR Runtime/Language 사전 점검" not in next_plan
    assert "schema_version" in output_schema
    assert "docs/schema/manifest.schema.json" in output_schema
    assert "text_blocks_rag.jsonl" in output_schema
    assert "semantic_units_rag.jsonl" in output_schema
    assert "requirements_rag.jsonl" in output_schema
    assert "cross_refs_rag.jsonl" in output_schema
    assert "retrieval_chunks_rag.jsonl" in output_schema
    assert "source_sha256" in output_schema
    assert "figures_rag.jsonl" in output_schema
    assert "domain_units_rag.jsonl" in output_schema
    assert "requirement_traceability_rag.jsonl" in output_schema
    assert "technical_tables_rag.jsonl" in output_schema
    assert "corpus_manifest.json" in output_schema
    assert "corpus_diff_report.json" in output_schema
    assert "requirement_change_impact_report.json" in output_schema
    assert "tables_rag.jsonl" in output_schema
    assert "pdf2md --help" in output_schema
    assert "94/100" in quality_scorecard
    assert "Q31. Local Corpus Profile Runner" in quality_scorecard
    assert "Q35. Rendered Diagram Fixture Suite" in quality_scorecard


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
