from __future__ import annotations

from pathlib import Path


def test_readme_is_concise_project_hub() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert len(readme.splitlines()) <= 220
    assert max(len(line) for line in readme.splitlines()) <= 240
    assert "PDF 문서를 **원문 보존 중심 Markdown**으로 변환" in readme
    assert "핵심 원칙과 지원 범위" not in readme
    assert "AI Agent 연동 지원" in readme
    assert "python3 -m pdf2md input.pdf" in readme
    assert "python3 -m pdf2md --input-dir ./pdfs --skip-existing" in readme
    assert "python3 -m pdf2md input.pdf -o output/ --password secret" in readme
    assert "<pdf_stem>_output/" in readme
    assert "document.md" in readme
    assert "manifest.json" in readme
    assert "report.json" in readme
    assert "text_blocks_rag.jsonl" in readme
    assert "technical_tables_rag.jsonl" in readme
    assert "retrieval_chunks_rag.jsonl" in readme
    assert "docs/WINDOWS_INSTALL_RUN_QUICKSTART.md" in readme
    assert "docs/WINDOWS_A_TO_Z_GUIDE.md" in readme
    assert "docs/MACOS_GUI_QUICKSTART.md" in readme
    assert "docs/GUI_USER_GUIDE.md" in readme
    assert "docs/OUTPUT_SCHEMA.md" in readme
    assert "docs/RAG_INDEXER_INTEGRATION_RECIPES.md" in readme
    assert "docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md" in readme
    assert "mcp_server.py" in readme
    assert "agent-pack/" in readme
    assert "pdf2md-rag-ingest/" in readme
    assert "agent-adapters/" in readme
    assert "docs/AGENT_SKILL_USAGE_GUIDE.md" in readme
    assert "docs/AGENT_SKILL_PORTABILITY.md" in readme
    assert "docs/MCP_SERVER_INSTALL_USAGE_GUIDE.md" in readme
    assert "scripts/install_agent_skill_pack.py" in readme
    assert 'python -m pip install -e ".[dev]"' in readme
    assert 'python -m pip install -e ".[mcp]"' in readme
    assert 'python -m pip install -e ".[dev,mcp]"' in readme
    assert "Claude Code, Cline, Roo Code, Cursor, Continue" in readme
    assert 'PDF2MD_MCP_ROOTS="/path/to/project:/path/to/pdfs:/path/to/output"' in readme
    assert "`pdf2md`/`pdf2md-gui`/`pdf2md-mcp` console script metadata" in readme
    assert "summary.page_cache_hits" not in readme
    assert "Open Corpus Diff" not in readme
    assert "runtime diagnostic code/message/action" not in readme
    assert "pdf/v10" not in readme
    assert "metadata.py" not in readme
    assert "html_table.py" not in readme


def test_user_facing_markdown_docs_use_portable_links_and_quoted_extras() -> None:
    docs = [
        Path("README.md"),
        Path("docs/AGENT_SKILL_USAGE_GUIDE.md"),
        Path("docs/AGENT_SKILL_PORTABILITY.md"),
        Path("docs/GUI_USER_GUIDE.md"),
        Path("docs/MACOS_GUI_QUICKSTART.md"),
        Path("docs/MCP_SERVER_DEVELOPMENT_SPEC.md"),
        Path("docs/MCP_SERVER_INSTALL_USAGE_GUIDE.md"),
        Path("docs/WINDOWS_A_TO_Z_GUIDE.md"),
        Path("docs/WINDOWS_INSTALL_RUN_QUICKSTART.md"),
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "/Users/mankiw/VS_Project/ConvertPdfToMarkdown" not in text
        assert "pip install -e .[dev]" not in text
        assert "python -m pip install -e .[dev]" not in text
        assert "python3 -m pip install -e .[dev]" not in text


def test_nvme_base_and_command_spec_contracts_are_documented() -> None:
    output_schema = Path("docs/OUTPUT_SCHEMA.md").read_text(encoding="utf-8")
    rag_recipes = Path("docs/RAG_INDEXER_INTEGRATION_RECIPES.md").read_text(encoding="utf-8")
    agent_guide = Path("docs/AGENT_SKILL_USAGE_GUIDE.md").read_text(encoding="utf-8")
    nvme_spec = Path("docs/NVME_BASE_RAG_ADAPTER_DEVELOPMENT_SPEC.md").read_text(encoding="utf-8")

    assert "NVMe Base and NVM Command Set specs use the same candidate contract" in output_schema
    assert "latest_nvme_spec_benchmark_report.json" in output_schema
    assert "`spec_document_type`: `base` or `nvm_command_set`" in output_schema
    assert "`command_set_eval` is metrics-only" in output_schema
    assert "--spec-document nvm_command_set" in rag_recipes
    assert "--fail-on-command-eval-error" in rag_recipes
    assert "NVM Command Set도 같은 `technical_spec_rag + domain_adapter=nvme` contract" in rag_recipes
    assert "query/result 원문 없이 aggregate metric만 기록" in nvme_spec
    assert "NVMe Base와 NVM Command Set은 모두 같은 `--domain-adapter nvme` 계약" in agent_guide
    assert "NVMe Base and Command Set RAG Adapter Development Spec" in nvme_spec
    assert "`spec_document_type`으로 `base`와 `nvm_command_set`을 구분" in nvme_spec


def test_ocp_datacenter_nvme_ssd_contract_is_documented() -> None:
    output_schema = Path("docs/OUTPUT_SCHEMA.md").read_text(encoding="utf-8")
    rag_recipes = Path("docs/RAG_INDEXER_INTEGRATION_RECIPES.md").read_text(encoding="utf-8")
    ocp_spec = Path("docs/OCP_DATACENTER_NVME_SSD_RAG_ADAPTER_DEVELOPMENT_SPEC.md").read_text(encoding="utf-8")
    ocp_handoff = Path("docs/OCP_SPEC_ANALYSIS_AGENT_HANDOFF.md").read_text(encoding="utf-8")

    assert "latest_ocp_datacenter_nvme_ssd_benchmark_report.json" in output_schema
    assert "technical_spec_rag + domain_adapter=ocp" in output_schema
    assert "`requirement_id`, `requirement_prefix`, `requirement_family`" in output_schema
    assert "`ocp_eval` records the P2 local query gate" in output_schema
    assert "run_latest_ocp_datacenter_nvme_ssd_benchmark.py" in rag_recipes
    assert "--ssd-agent-spec-type OCP --domain-adapter ocp" in rag_recipes
    assert "--fail-on-ocp-eval-error" in rag_recipes
    assert "Official source URL은 `https://www.opencompute.org/documents/datacenter-nvme-ssd-specification-v2-7-final-pdf-1`" in rag_recipes
    assert "OCP Datacenter NVMe SSD RAG Adapter Development Spec" in ocp_spec
    assert "P0-1: Official OCP benchmark wrapper and sanitized report model." in ocp_spec
    assert "OCP SpecAnalysisAgent Handoff" in ocp_handoff
    assert "`related_statistic_identifier`" in ocp_handoff
    assert "`ocp_eval`은 query/result 원문을 저장하지 않고 aggregate metric만 저장" in ocp_handoff


def test_q92_artifact_hygiene_and_maintenance_mapping_are_documented() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    tasks = Path("tasks.md").read_text(encoding="utf-8")

    assert "output/" in gitignore
    assert "*_output/" in gitignore
    assert "pdf2md/nvme_cmds/" in gitignore
    assert "M01은 Q93에서 1차 완료했다" in tasks
    assert "M02는 Q94에서 warning taxonomy registry 1차 정리를 완료했다" in tasks
    assert (
        "M03은 Q92에서 local artifact hygiene을 완료했고, Q95에서 CI/release gate 편의성 1차 정리, "
        "Q97에서 Python tooling/package readiness 1차 정리를 완료했다"
        in tasks
    )
    assert "M04는 Q92에서 active backlog와 문서 정합성 1차 정리를 완료했다" in tasks
    assert "M05는 Q95에서 lightweight CI gate를 보강했고, Q96에서 한글/OCR fixture 회귀 방어를 보강했다" in tasks
    assert (
        "M06은 Q98에서 structure marker OCR lazy 처리, Q99에서 page worker chunked parallelization, "
        "Q100에서 OCR page parallelization, Q101에서 adaptive table strategy, "
        "Q102에서 fast output profile과 sidecar scope를 완료했다"
        in tasks
    )
    assert (
        "M07은 Q103에서 이미지 파일 업로드가 불가능한 RAG 환경 대응, "
        "Q104에서 Docling 벤치마크 하네스, Q105에서 Docling-informed 확장 설계를 완료했다"
        in tasks
    )


def test_windows_guide_matches_cli_policy() -> None:
    guide = Path("docs/WINDOWS_A_TO_Z_GUIDE.md").read_text(encoding="utf-8")
    assert "docs\\WINDOWS_INSTALL_RUN_QUICKSTART.md" in guide
    assert "python -m pdf2md .\\sample.pdf" in guide
    assert "sample_output\\document.md" in guide
    assert "python -m pdf2md --input-dir .\\pdfs --skip-existing" in guide
    assert "python -m pdf2md .\\sample.pdf -o .\\output --password secret" in guide
    assert "py -3.11 -m venv .venv311" in guide
    assert "py -3.14 -m venv .venv314" in guide
    assert "scripts\\setup_windows_env.ps1" in guide
    assert "scripts\\run_batch_folder_windows.ps1" in guide
    assert "Python 3.14 기본 / 3.11 fallback" in guide
    assert '.venv314\\Scripts\\python.exe -m pip install -e ".[dev]"' in guide
    assert "winget install --exact --id Python.Python.3.14" in guide
    assert ".\\scripts\\setup_windows_env.ps1 -PythonVersion 3.11 -VenvDir .venv311 -SkipWingetInstall" in guide
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
    assert "--min-expected-source-coverage" in guide
    assert "scripts\\check_ocr_runtime.py --ocr-lang kor+eng" in guide
    assert "scripts\\run_release_gates.py" in guide
    assert "--gates gui" in guide
    assert "scripts\\run_ssd_corpus_profile.py" in guide
    assert "scripts\\validate_ssd_rag_contract.py" in guide
    assert "requirement_change_impact_report.json" in guide
    assert "--ssd-agent-spec-type TCG" in guide
    assert "release_gate_report.json" in guide
    assert "--baseline-report pdf\\baseline\\corpus_eval_report.json" in guide
    assert "--max-duration-regression 0.2" in guide
    assert "docs\\OUTPUT_SCHEMA.md" in guide
    assert "docs\\schema\\manifest.schema.json" in guide
    assert "docs\\schema\\corpus_evidence_analysis_report.schema.json" in guide
    assert "scripts\\analyze_corpus_evidence_pack.py" in guide
    assert "scripts\\compare_corpus_evidence_packs.py" in guide
    assert "scripts\\export_output_schema.py --check" in guide
    assert "python -m build" in guide
    assert "benchmark_report.json" in guide
    assert "docs\\NEXT_QUALITY_IMPROVEMENT_PLAN.md" in guide
    assert "docs\\QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md" in guide
    assert "docs\\QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md" in guide
    assert "python -m pdf2md.gui" in guide
    assert "python -m pdf2md.gui --help" in guide
    assert "python -m pdf2md.gui --doctor" in guide
    assert "source checkout/editable/wheel packaging mode" in guide
    assert "Import profile / Export profile" in guide
    assert "Previous corpus manifest" in guide
    assert "Reuse unchanged" in guide
    assert "Open Corpus Diff" in guide
    assert "scripts\\run_gui_smoke_evidence.py" in guide
    assert "scripts\\run_gui_cli_parity.py" in guide
    assert "scripts\\benchmark_gui_cli_parity.py" in guide
    assert "scripts\\create_gui_support_bundle.py" in guide
    assert "wheel_contract_report.json" in guide
    assert "`pdf2md`/`pdf2md-gui`/`pdf2md-mcp` console script metadata" in guide
    assert "gui_cli_parity_report.json" in guide
    assert "gui_cli_benchmark_report.json" in guide
    assert "pdf2md.resources\\GUI_USER_GUIDE.md" in guide
    assert "gui_support_bundle.json" in guide
    assert "gui_smoke_evidence.json" in guide
    assert "--json-only" in guide
    assert "--gates gui-parity" in guide
    assert "--gates gui-benchmark" in guide
    assert "runtime diagnostic code/message/action" in guide
    assert "변환 warning message" in guide
    assert "pdf2md-gui" in guide
    assert "desktop GUI wrapper" in guide
    assert "docs\\GUI_USER_GUIDE.md" in guide
    assert "GUI의 `Help` 버튼" in guide
    assert "`기본 모드(원본 유지)`, `RAG 등록용(최적화)`, `기술 스펙 RAG`" in guide
    assert "`민감정보 보호 RAG`, `원본 유지 + sidecar`, `Optimize Options(유저 선택)`" in guide
    assert "percent text" in guide
    assert "page-level percent" in guide
    assert "pages/sec" in guide
    assert "elapsed time" in guide
    assert "`Cancel`을 누르면 현재 문서가 끝난 뒤" in guide
    assert "`Open Manifest`" in guide
    assert "`Clear recent`" in guide
    assert "ZIP/source checkout" in guide
    assert "PyInstaller/native bundle" in guide
    assert "GUI에서 output folder 오류" in guide
    assert "- Git\n  - `git clone`, `git pull` 같은 저장소 동기화 흐름에서만 필요" in guide


def test_windows_quickstart_covers_install_cli_and_gui() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    guide = Path("docs/WINDOWS_INSTALL_RUN_QUICKSTART.md").read_text(encoding="utf-8")
    gui_guide = Path("docs/GUI_USER_GUIDE.md").read_text(encoding="utf-8")

    assert "docs/WINDOWS_INSTALL_RUN_QUICKSTART.md" in readme
    assert "docs/WINDOWS_INSTALL_RUN_QUICKSTART.md" in gui_guide
    assert ".\\scripts\\setup_windows_env.bat" in guide
    assert 'python -m pip install -e ".[dev]"' in guide
    assert "python -m pdf2md .\\sample.pdf" in guide
    assert "python -m pdf2md --input-dir .\\pdfs" in guide
    assert ".\\scripts\\run_batch_folder_windows.bat -InputDir .\\pdfs" in guide
    assert "python -m pdf2md.gui" in guide
    assert "pdf2md-gui" in guide
    assert "python -m pdf2md.gui --doctor" in guide
    assert "이미지 업로드 불가 RAG 대응" in guide
    assert "--rag-profile technical_spec_rag_visual --image-mode placeholder" in guide
    assert "Domain=manual" in guide
    assert "Python 3.14`와 `.venv314`" in guide
    assert "winget`으로 `Python.Python.3.14` 설치" in guide
    assert ".\\scripts\\setup_windows_env.ps1 -PythonVersion 3.14 -VenvDir .venv314 -RecreateVenv" in guide
    assert "retrieval_chunks_rag.jsonl" in guide
    assert "figures_rag.jsonl" in guide
    assert "tesseract --version" in guide
    assert "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned" in guide
    assert "git pull origin main" in guide


def test_macos_gui_quickstart_is_non_developer_friendly() -> None:
    guide = Path("docs/MACOS_GUI_QUICKSTART.md").read_text(encoding="utf-8")
    assert "python3 --version" in guide
    assert "Python 3.11.x" in guide
    assert 'python -m pip install -e ".[dev]"' in guide
    assert "python -m pdf2md.gui" in guide
    assert "pdf2md-gui" in guide
    assert "python -m pdf2md.gui --help" in guide
    assert "python -m pdf2md.gui --doctor" in guide
    assert "tcl_tk_patchlevel_available" in guide
    assert "Expert options" in guide
    assert "Export profile" in guide
    assert "scripts/run_gui_smoke_evidence.py" in guide
    assert "scripts/run_gui_cli_parity.py" in guide
    assert "scripts/benchmark_gui_cli_parity.py" in guide
    assert "scripts/create_gui_support_bundle.py" in guide
    assert "scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-gui --gates gui" in guide
    assert "scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-gui-parity --gates gui-parity" in guide
    assert "scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-gui-benchmark --gates gui-benchmark" in guide
    assert "pdf2md.resources/GUI_USER_GUIDE.md" in guide
    assert "gui_support_bundle.json" in guide
    assert "gui_smoke_evidence.json" in guide
    assert "gui_cli_parity_report.json" in guide
    assert "gui_cli_benchmark_report.json" in guide
    assert "--json-only" in guide
    assert "GUI runtime doctor diagnostics" in guide
    assert "workspace/home absolute path" in guide
    assert "docs/GUI_USER_GUIDE.md" in guide
    assert "`Help` 버튼" in guide
    assert "`English`로 바꿨을 때" in guide
    assert "percent text" in guide
    assert "page-level callback" in guide
    assert "pages_per_second" in guide
    assert "Cancel" in guide
    assert "Open Markdown" in guide
    assert "Clear recent" in guide
    assert "local-only state" in guide
    assert "로컬 GUI smoke checklist" in guide
    assert "PyInstaller/native bundle" in guide
    assert "`success`, `partial_success`, `failed`, `skipped`, `cancelled`" in guide
    assert "Retry" in guide
    assert "previous corpus manifest path" in guide
    assert "원문 텍스트, 표, 이미지 내용은 GUI summary에서 요약하지 않는다" in guide
    assert "tesseract --version" in guide


def test_gui_user_guide_is_separate_from_cli_docs() -> None:
    guide = Path("docs/GUI_USER_GUIDE.md").read_text(encoding="utf-8")
    assert "GUI 사용자 가이드" in guide
    assert "CLI가 익숙하지 않은 사용자" in guide
    assert "python -m pdf2md.gui" in guide
    assert "pdf2md-gui" in guide
    assert "python -m pdf2md.gui --doctor" in guide
    assert "--doctor-format json" in guide
    assert "Expert options" in guide
    assert "invalid profile" in guide
    assert "scripts/run_gui_smoke_evidence.py" in guide
    assert "scripts/run_gui_cli_parity.py" in guide
    assert "scripts/benchmark_gui_cli_parity.py" in guide
    assert "scripts/create_gui_support_bundle.py" in guide
    assert "wheel_contract_report.json" in guide
    assert "`pdf2md`/`pdf2md-gui`/`pdf2md-mcp` console script metadata" in guide
    assert "gui_cli_parity_report.json" in guide
    assert "gui_cli_benchmark_report.json" in guide
    assert "pdf2md.resources/GUI_USER_GUIDE.md" in guide
    assert "gui_support_bundle.json" in guide
    assert "gui_smoke_evidence.json" in guide
    assert "원문 PDF 텍스트, 표 내용, 이미지 내용" in guide
    assert "GUI runtime doctor diagnostics" in guide
    assert "horizontal scrollbar" in guide
    assert "Help" in guide
    assert "`PDF file`" in guide
    assert "`PDF folder`" in guide
    assert "`Output folder`" in guide
    assert "기본 언어는 한국어" in guide
    assert "`RAG 등록용(최적화)`" in guide
    assert "`2/10 (20%)`" in guide
    assert "`Status`" in guide
    assert "`Warnings`" in guide
    assert "`Retry`" in guide
    assert "`cancelled`" in guide
    assert "`Open Manifest`" in guide
    assert "`Open Corpus Manifest`" in guide
    assert "`Open Corpus Diff`" in guide
    assert "`Open Requirement Impact`" in guide
    assert "`Clear recent`" in guide
    assert "local-only JSON state" in guide
    assert "previous corpus manifest path는 profile이나 recent state에 저장하지 않는다" in guide
    assert "page-level 진행률 callback" in guide
    assert "pages_per_second" in guide
    assert "elapsed_ms" in guide
    assert "원문 텍스트, 표, 이미지 내용을 요약하거나 재서술하지 않는다" in guide
    assert "자동화, CI, 반복 스크립트 실행은 GUI보다 CLI를 권장" in guide
    assert "--gates gui-parity" in guide
    assert "--gates gui-benchmark" in guide


def test_ci_and_next_plan_contracts_are_present() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    next_plan = Path("docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md").read_text(encoding="utf-8")
    development_specs = Path("docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md").read_text(encoding="utf-8")
    implemented_specs = Path("docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md").read_text(encoding="utf-8")
    docling_design = Path("docs/DOCLING_INFORMED_EXTENSION_DESIGN.md").read_text(encoding="utf-8")
    output_schema = Path("docs/OUTPUT_SCHEMA.md").read_text(encoding="utf-8")
    quality_scorecard = Path("docs/QUALITY_SCORECARD.md").read_text(encoding="utf-8")
    native_migration_spec = Path("docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md").read_text(
        encoding="utf-8"
    )
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    mcp_nvme_stability_spec = Path("docs/archive/PDF2MD_MCP_NVME_BASE_STABILITY_DEVELOPMENT_SPEC.md").read_text(
        encoding="utf-8"
    )

    assert "python-version" in workflow
    assert '"3.11"' in workflow
    assert "python -m pytest" in workflow
    assert "python scripts/export_output_schema.py --check" in workflow
    assert "tests/test_docs_examples.py tests/test_output_schema_contract.py" in workflow
    assert "python -m pdf2md --help" in workflow
    assert "앞으로 작업할 항목만" in next_plan
    assert "작업이 완료되고 테스트 통과 및 PR merge까지 끝나면" in next_plan
    assert "구현 완료, 테스트 통과, PR merge까지 끝난 항목은" in next_plan
    assert "docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md" in next_plan
    assert "docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md" in next_plan
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
    assert "Q35. Rendered Diagram Fixture Suite" not in next_plan
    assert "Q36. Page-Level Parallel Extractor" not in next_plan
    assert "Q42. Full Page Worker Table Candidate Parallelization" not in next_plan
    assert "Q43. Quality Scorecard Refresh" not in next_plan
    assert "Q46. RAG Golden Query Expected Source Coverage" not in next_plan
    assert "Q44. Domain Technical Table Coverage Expansion" not in next_plan
    assert "Q47. Local Technical Corpus Evidence Pack" not in next_plan
    assert "Q48. Corpus Evidence Signature Analysis Report" not in next_plan
    assert "Q49. Appendix Clause Requirement Fixture Expansion" not in next_plan
    assert "Q50. Captionless Diagram Diagnostics Hardening" not in next_plan
    assert "Q51. Evidence Pack History Comparison Gate" not in next_plan
    assert "Q52. Quality Document And Schema History Contract" not in next_plan
    assert "Q53. Minimal Desktop GUI Wrapper" not in next_plan
    assert "Q54. GUI Runtime And Install Diagnostics" not in next_plan
    assert "Q55. GUI Conversion Result Review UX" not in next_plan
    assert "Q56. GUI Batch Operation Controls" not in next_plan
    assert "Q57. Non-Developer GUI Distribution Guide" not in next_plan
    assert "Q58. GUI Smoke And Contract Test Expansion" not in next_plan
    assert "Q59. GUI User Guide And Help Entry" not in next_plan
    assert "Q60. GUI Practical UX And Distribution Hardening" not in next_plan
    assert "### P1 / Q61. GUI Localization, Presets, And Progress Percent" not in next_plan
    assert "Q62. GUI Smoke Evidence And Layout Guardrails" not in next_plan
    assert "Q64. Responsive GUI Layout And Accessibility Guardrails" not in next_plan
    assert "Q65. GUI Runtime Doctor And Packaging Compatibility Smoke" not in next_plan
    assert "Q66. Sanitized GUI Support Bundle" not in next_plan
    assert "Q67. GUI Expert Options And Profile Import/Export" not in next_plan
    assert "Q68. GUI Release Gate Integration" not in next_plan
    assert "Q69. Wheel Contents And GUI Help Resource Contract" not in next_plan
    assert "Q70. GUI Profile And Support Bundle Failure Fixture" not in next_plan
    assert "Q71. Quality Scorecard Refresh And Next Backlog Reassessment" not in next_plan
    assert "Tcl/Tk patchlevel" not in next_plan
    assert "Q90. Cross Reference Target Index Expansion" not in next_plan
    assert "PDF outline/bookmark" not in next_plan
    assert "List of Figures" not in next_plan
    assert "Q92. Active Backlog And Local Artifact Hygiene" not in next_plan
    assert "Q93. Pipeline Stage And Output Responsibility Split" not in next_plan
    assert "Q94. Warning And Reason Taxonomy Contract" not in next_plan
    assert "Q95. Lightweight CI And Release Gate Coverage" not in next_plan
    assert "Q96. Korean, OCR, And Image-Only Golden Promotion" not in next_plan
    assert "Q97. Modern Python Tooling And Packaging Readiness" not in next_plan
    assert "Q98. Lazy Structure Marker OCR" not in next_plan
    assert "Q99. Page Worker Chunked Parallelization" not in next_plan
    assert "Q100. OCR Page Parallelization" not in next_plan
    assert "Q101. Table Strategy Adaptive Mode" not in next_plan
    assert "Q102. Fast Output Profile And Sidecar Scope" not in next_plan
    assert "Q103. Assetless Technical RAG Figure Text Chunks" not in next_plan
    assert "Q104. Docling Benchmark Harness And Comparison Pack" not in next_plan
    assert "Q105. Docling-Informed OCR And Layout Extension Design" not in next_plan
    assert "Q106. GUI Assetless RAG Preset And Manual Domain Adapter" not in next_plan
    assert "Q107. Assetless Figure Visual Semantics Layer" not in next_plan
    assert "Q108. Latest NVMe Command Set Benchmark Evidence Path" not in next_plan
    assert "Q109. Docling-Installed Benchmark Gate" not in next_plan
    assert "Q110. Multi OCR Backend Runtime Probe" not in next_plan
    assert "Q111. OCR Backend Adapter Contract" not in next_plan
    assert "Q112. Region OCR Report-Only Prototype" not in next_plan
    assert "Q113. Local-Only Figure Description Evaluation Pack" not in next_plan
    assert "Q114. Docling Layout Adapter Comparison Mode" not in next_plan
    assert "Q115. Visual Technical Spec RAG Profile and Metrics" not in next_plan
    assert "Q116. SSD Verification Agent PDF2MD Sidecar Handoff" not in next_plan
    assert "Q117. MCP NVMe Base Large Conversion Stability" not in next_plan
    assert "현재 남은 작업 없음." in next_plan
    assert "Q118. Native Document IR and Serializer Boundary" not in next_plan
    assert "Q119. Table Confidence v2" not in next_plan
    assert "Q120. Native Hybrid Chunking v2" not in next_plan
    assert "Q121. Layout Sidecar and Reading Order Diagnostics" not in next_plan
    assert "Q122. Region OCR Evidence v2" not in next_plan
    assert "Q123. OCR Backend Registry Expansion" not in next_plan
    assert "Q124. Figure Semantics v2" not in next_plan
    assert "Q125. Domain Adapter Registry Hardening" not in next_plan
    assert "docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md" not in next_plan
    assert "Q85. RAG Preset Status And Warning Severity Calibration" not in next_plan
    assert "Q86. Full Technical Spec Table Quality Triage And Recovery" not in next_plan
    assert "Q87. Technical Spec RAG Preset Domain Profile UX" not in next_plan
    assert "Q88. Storage And Security Domain Adapter Expansion" not in next_plan
    assert "Q89. Real Corpus Preset Evaluation And Score Gate" not in next_plan
    assert "Q81. Structure Marker OCR Early Stop And Cache" not in next_plan
    assert "Q82. Expected Table Fallback Severity Taxonomy" not in next_plan
    assert "Q83. Real Corpus Cross Reference Precision" not in next_plan
    assert "Q84. Release Readiness Sweep" not in next_plan
    assert "Q77. RAG Sibling Chunk Merge" not in next_plan
    assert "Q78. RAG Chunk Relationship Metadata" not in next_plan
    assert "Q79. Purpose-Specific RAG Profiles" not in next_plan
    assert "Q72. Shared Batch Runner And GUI Batch Artifact Parity" not in next_plan
    assert "Q73. GUI Incremental Corpus Options" not in next_plan
    assert "Q74. CLI/GUI Golden Parity Gate" not in next_plan
    assert "Q75. GUI Metrics And Page Progress Contract" not in next_plan
    assert "Q76. CLI/GUI Performance Benchmark Report" not in next_plan
    assert "Q01. 실문서 Corpus 품질 게이트 고도화" not in next_plan
    assert "Q05. OCR Runtime/Language 사전 점검" not in next_plan
    assert "현재 Active Development Specs" in development_specs
    assert "Q90. Cross Reference Target Index Expansion" not in development_specs
    assert "Q92. Active Backlog And Local Artifact Hygiene" not in development_specs
    assert "Q93. Pipeline Stage And Output Responsibility Split" not in development_specs
    assert "Q94. Warning And Reason Taxonomy Contract" not in development_specs
    assert "Q95. Lightweight CI And Release Gate Coverage" not in development_specs
    assert "Q96. Korean, OCR, And Image-Only Golden Promotion" not in development_specs
    assert "Q97. Modern Python Tooling And Packaging Readiness" not in development_specs
    assert "cross_ref_resolved_coverage >= 0.90" not in development_specs
    assert "PDF outline/bookmark section fallback" not in development_specs
    assert "Register/capability false-positive suppression" not in development_specs
    assert "Q98. Lazy Structure Marker OCR" not in development_specs
    assert "Q99. Page Worker Chunked Parallelization" not in development_specs
    assert "Q100. OCR Page Parallelization" not in development_specs
    assert "Q101. Table Strategy Adaptive Mode" not in development_specs
    assert "Q102. Fast Output Profile And Sidecar Scope" not in development_specs
    assert "Q103. Assetless Technical RAG Figure Text Chunks" not in development_specs
    assert "Q104. Docling Benchmark Harness And Comparison Pack" not in development_specs
    assert "Q105. Docling-Informed OCR And Layout Extension Design" not in development_specs
    assert "Q106. GUI Assetless RAG Preset And Manual Domain Adapter" not in development_specs
    assert "Q107. Assetless Figure Visual Semantics Layer" not in development_specs
    assert "Q108. Latest NVMe Command Set Benchmark Evidence Path" not in development_specs
    assert "Q109. Docling-Installed Benchmark Gate" not in development_specs
    assert "Q110. Multi OCR Backend Runtime Probe" not in development_specs
    assert "Q111. OCR Backend Adapter Contract" not in development_specs
    assert "Q112. Region OCR Report-Only Prototype" not in development_specs
    assert "Q113. Local-Only Figure Description Evaluation Pack" not in development_specs
    assert "Q114. Docling Layout Adapter Comparison Mode" not in development_specs
    assert "Q115. Visual Technical Spec RAG Profile and Metrics" not in development_specs
    assert "Q116. SSD Verification Agent PDF2MD Sidecar Handoff" not in development_specs
    assert "Q117. MCP NVMe Base Large Conversion Stability" not in development_specs
    assert "figure_descriptions_rag.jsonl" not in development_specs
    assert "figure_structures_rag.jsonl" not in development_specs
    assert "--rag-generated-figure-descriptions" not in development_specs
    assert "generated_text=true" not in development_specs
    assert "placeholder + figure_text chunk" not in development_specs
    assert "다중 OCR backend" not in development_specs
    assert "현재 active 개발 명세 없음." in development_specs
    assert "Q118. Native Document IR and Serializer Boundary" not in development_specs
    assert "Q119. Table Confidence v2" not in development_specs
    assert "Q120. Native Hybrid Chunking v2" not in development_specs
    assert "Q121. Layout Sidecar and Reading Order Diagnostics" not in development_specs
    assert "Q122. Region OCR Evidence v2" not in development_specs
    assert "Q123. OCR Backend Registry Expansion" not in development_specs
    assert "Q124. Figure Semantics v2" not in development_specs
    assert "Q125. Domain Adapter Registry Hardening" not in development_specs
    assert "PDF2MD Native Migration Plan" not in development_specs
    assert "Q85. RAG Preset Status And Warning Severity Calibration" not in development_specs
    assert "Q86. Full Technical Spec Table Quality Triage And Recovery" not in development_specs
    assert "Q87. Technical Spec RAG Preset Domain Profile UX" not in development_specs
    assert "Q88. Storage And Security Domain Adapter Expansion" not in development_specs
    assert "Q89. Real Corpus Preset Evaluation And Score Gate" not in development_specs
    assert "Q81. Structure Marker OCR Early Stop And Cache" not in development_specs
    assert "Q82. Expected Table Fallback Severity Taxonomy" not in development_specs
    assert "Q83. Real Corpus Cross Reference Precision" not in development_specs
    assert "Q84. Release Readiness Sweep" not in development_specs
    assert "Q77. RAG Sibling Chunk Merge" not in development_specs
    assert "Q78. RAG Chunk Relationship Metadata" not in development_specs
    assert "Q79. Purpose-Specific RAG Profiles" not in development_specs
    assert "merge_sibling_text_chunks" not in development_specs
    assert "previous_chunk_id" not in development_specs
    assert "Q72. Shared Batch Runner And GUI Batch Artifact Parity" not in development_specs
    assert "Q73. GUI Incremental Corpus Options" not in development_specs
    assert "Q74. CLI/GUI Golden Parity Gate" not in development_specs
    assert "Q75. GUI Metrics And Page Progress Contract" not in development_specs
    assert "Q76. CLI/GUI Performance Benchmark Report" not in development_specs
    assert "scripts/run_gui_cli_parity.py" not in development_specs
    assert "scripts/benchmark_gui_cli_parity.py" not in development_specs
    assert "Q54. GUI Runtime And Install Diagnostics" not in development_specs
    assert "Q55. GUI Conversion Result Review UX" not in development_specs
    assert "Q56. GUI Batch Operation Controls" not in development_specs
    assert "Q57. Non-Developer GUI Distribution Guide" not in development_specs
    assert "Q58. GUI Smoke And Contract Test Expansion" not in development_specs
    assert "Q59. GUI User Guide And Help Entry" not in development_specs
    assert "Q60. GUI Practical UX And Distribution Hardening" not in development_specs
    assert "### P1 / Q61. GUI Localization, Presets, And Progress Percent" not in development_specs
    assert "Q62. GUI Smoke Evidence And Layout Guardrails" not in development_specs
    assert "Q64. Responsive GUI Layout And Accessibility Guardrails" not in development_specs
    assert "Q65. GUI Runtime Doctor And Packaging Compatibility Smoke" not in development_specs
    assert "Q66. Sanitized GUI Support Bundle" not in development_specs
    assert "Q67. GUI Expert Options And Profile Import/Export" not in development_specs
    assert "Q68. GUI Release Gate Integration" not in development_specs
    assert "Q69. Wheel Contents And GUI Help Resource Contract" not in development_specs
    assert "Q70. GUI Profile And Support Bundle Failure Fixture" not in development_specs
    assert "Q71. Quality Scorecard Refresh And Next Backlog Reassessment" not in development_specs
    assert "Q74. CLI/GUI Golden Parity Gate" not in development_specs
    assert "Q75. GUI Metrics And Page Progress Contract" not in development_specs
    assert "Q76. CLI/GUI Performance Benchmark Report" not in development_specs
    assert "tests/test_gui_profiles.py" not in development_specs
    assert "Q44. Domain Technical Table Coverage Expansion" not in development_specs
    assert "Q46. RAG Golden Query Expected Source Coverage" not in development_specs
    assert "Q47. Local Technical Corpus Evidence Pack" not in development_specs
    assert "Q48. Corpus Evidence Signature Analysis Report" not in development_specs
    assert "Q52. Quality Document And Schema History Contract" not in development_specs
    assert "Q53. Minimal Desktop GUI Wrapper" not in development_specs
    assert "docs/PDF2MD_MCP_NVME_BASE_STABILITY_DEVELOPMENT_SPEC.md" not in next_plan
    assert "true no-image mode" not in next_plan
    assert "image/figure extraction timeout" not in next_plan
    assert "docs/PDF2MD_MCP_NVME_BASE_STABILITY_DEVELOPMENT_SPEC.md" not in development_specs
    assert "image_mode=none" not in development_specs
    assert "MCP page-window conversion" not in development_specs
    assert "Status: Implemented Q117 development spec." in mcp_nvme_stability_spec
    assert "ImageMode.PLACEHOLDER" in mcp_nvme_stability_spec
    assert "P0-1. True No-Image Mode" in mcp_nvme_stability_spec
    assert "P0-3. Page-Window Batch Conversion and Merge Contract" in mcp_nvme_stability_spec
    assert "interrupted_report.json" in mcp_nvme_stability_spec
    assert "page_window_merge_report.json" in mcp_nvme_stability_spec
    assert "완료된 Q34-Q125" in development_specs
    assert "Quality Improvement Implemented Specs" in implemented_specs
    assert "Q125. Domain Adapter Registry Hardening" in implemented_specs
    assert "adapter_metadata" in implemented_specs
    assert "cross_spec_compatibility" in implemented_specs
    assert "DomainAdapterSpec" in implemented_specs
    assert "Q124. Figure Semantics v2" in implemented_specs
    assert "observed_text" in implemented_specs
    assert "generated_content_scope" in implemented_specs
    assert "hallucination_risk" in implemented_specs
    assert "relationship_hints" in implemented_specs
    assert "Q122. Region OCR Evidence v2" in implemented_specs
    assert "figure_ocr_evidence_rag.jsonl" in implemented_specs
    assert "Q121. Layout Sidecar and Reading Order Diagnostics" in implemented_specs
    assert "page_layout_rag.jsonl" in implemented_specs
    assert "Q120. Native Hybrid Chunking v2" in implemented_specs
    assert "relationship_metadata_version" in implemented_specs
    assert "context_metadata" in implemented_specs
    assert "Q119. Table Confidence v2" in implemented_specs
    assert "table_confidence_v2" in implemented_specs
    assert "Q118. Native Document IR and Serializer Boundary" in implemented_specs
    assert "pdf2md/document_ir.py" in implemented_specs
    assert "ir_text_block_records" in implemented_specs
    assert "Q117. MCP NVMe Base Large Conversion Stability" in implemented_specs
    assert "docs/archive/PDF2MD_MCP_NVME_BASE_STABILITY_DEVELOPMENT_SPEC.md" in implemented_specs
    assert "conversion_state.json" in implemented_specs
    assert "interrupted_report.json" in implemented_specs
    assert "pdf2md_convert_pdf_windowed" in implemented_specs
    assert "Q115. Visual Technical Spec RAG Profile and Metrics" in implemented_specs
    assert "Q116. SSD Verification Agent PDF2MD Sidecar Handoff" in implemented_specs
    assert "technical_spec_rag_visual" in implemented_specs
    assert "scripts/visual_rag_eval.py" in implemented_specs
    assert "ingest_pdf2md_sidecars" in implemented_specs
    assert "Q114. Docling Layout Adapter Comparison Mode" in implemented_specs
    assert "layout_comparison_mode" in implemented_specs
    assert "--layout-comparison-mode" in implemented_specs
    assert "Q113. Local-Only Figure Description Evaluation Pack" in implemented_specs
    assert "figure_description_eval_report.json" in implemented_specs
    assert "evaluate_figure_descriptions.py" in implemented_specs
    assert "--gates figure-description-eval" in implemented_specs
    assert "Q112. Region OCR Report-Only Prototype" in implemented_specs
    assert "region_ocr.report_only=true" in implemented_specs
    assert "Q111. OCR Backend Adapter Contract" in implemented_specs
    assert "pdf2md/extractors/ocr_backends/" in implemented_specs
    assert "Q123. OCR Backend Registry Expansion" in implemented_specs
    assert "pdf2md/extractors/ocr_backends/tesseract_cli.py" in implemented_specs
    assert "ocr_backend_raw_confidence_unit" in implemented_specs
    assert "Q110. Multi OCR Backend Runtime Probe" in implemented_specs
    assert "probe_ocr_backends.py" in implemented_specs
    assert "Q109. Docling-Installed Benchmark Gate" in implemented_specs
    assert "docling_required_not_available" in implemented_specs
    assert "Q108. Latest NVMe Command Set Benchmark Evidence Path" in implemented_specs
    assert "run_latest_nvme_command_set_eval.py" in implemented_specs
    assert "Q107. Assetless Figure Visual Semantics Layer" in implemented_specs
    assert "figure_descriptions_rag.jsonl" in implemented_specs
    assert "figure_structures_rag.jsonl" in implemented_specs
    assert "generated_text=true" in implemented_specs
    assert "Q105. Docling-Informed OCR And Layout Extension Design" in implemented_specs
    assert "Q106. GUI Assetless RAG Preset And Manual Domain Adapter" in implemented_specs
    assert "PDF2MD Native Migration Development Spec" in native_migration_spec
    assert "Docling은 필수 dependency로 추가하지 않는다." in native_migration_spec
    assert "Q118 - Native Document IR and Serializer Boundary" in native_migration_spec
    assert "Q119 - Table Confidence v2" in native_migration_spec
    assert "Q120 - Native Hybrid Chunking v2" in native_migration_spec
    assert "Q121 - Layout Sidecar and Reading Order Diagnostics" in native_migration_spec
    assert "Q122 - Region OCR Evidence v2" in native_migration_spec
    assert "Q123 - OCR Backend Registry Expansion" in native_migration_spec
    assert "Q124 - Figure Semantics v2" in native_migration_spec
    assert "Q125 - Domain Adapter Registry Hardening" in native_migration_spec
    assert "Docling runtime dependency 추가" in native_migration_spec
    assert "generated description을 `document.md` 본문에 삽입" in native_migration_spec
    assert "manual_domain_adapter_keywords" in implemented_specs
    assert "DOCLING_INFORMED_EXTENSION_DESIGN.md" in implemented_specs
    assert "Q113에서 local-only picture description evaluation pack" in docling_design
    assert "Q114에서 Docling layout adapter comparison mode를 완료했다" in docling_design
    assert "1. Docling layout adapter comparison mode" not in docling_design
    assert "DocumentConverter().convert" in docling_design
    assert "raw_content_included=false" in docling_design
    assert "generated_description" in docling_design
    assert "Q104. Docling Benchmark Harness And Comparison Pack" in implemented_specs
    assert "docling_benchmark_report.json" in implemented_specs
    assert "Q103. Assetless Technical RAG Figure Text Chunks" in implemented_specs
    assert "figure_text_chunk_record_count" in implemented_specs
    assert "Q34. Offline Index Contract Validator" in implemented_specs
    assert "Q42. Full Page Worker Table Candidate Parallelization" in implemented_specs
    assert "Q46. RAG Golden Query Expected Source Coverage" in implemented_specs
    assert "Q77. RAG Sibling Chunk Merge" in implemented_specs
    assert "Q78. RAG Chunk Relationship Metadata" in implemented_specs
    assert "Q79. Purpose-Specific RAG Profiles" in implemented_specs
    assert "Q80. Real Corpus Structure Marker OCR And Provenance Hardening" in implemented_specs
    assert "Q81. Structure Marker OCR Early Stop And Cache" in implemented_specs
    assert "Q82. Expected Table Fallback Severity Taxonomy" in implemented_specs
    assert "Q83. Real Corpus Cross Reference Precision" in implemented_specs
    assert "Q84. Release Readiness Sweep" in implemented_specs
    assert "Q85. RAG Preset Status And Warning Severity Calibration" in implemented_specs
    assert "Q86. Full Technical Spec Table Quality Triage And Recovery" in implemented_specs
    assert "Q87. Technical Spec RAG Preset Domain Profile UX" in implemented_specs
    assert "Q88. Storage And Security Domain Adapter Expansion" in implemented_specs
    assert "Q89. Real Corpus Preset Evaluation And Score Gate" in implemented_specs
    assert "Q90. Cross Reference Target Index Expansion" in implemented_specs
    assert "cross_ref_resolved_coverage=0.9923" in implemented_specs
    assert "Q91. Q90 Output Schema Contract Alignment" in implemented_specs
    assert "Q92. Active Backlog And Local Artifact Hygiene" in implemented_specs
    assert "Q93. Pipeline Stage And Output Responsibility Split" in implemented_specs
    assert "Q94. Warning And Reason Taxonomy Contract" in implemented_specs
    assert "Q95. Lightweight CI And Release Gate Coverage" in implemented_specs
    assert "Q96. Korean, OCR, And Image-Only Golden Promotion" in implemented_specs
    assert "Q97. Modern Python Tooling And Packaging Readiness" in implemented_specs
    assert "Q98. Lazy Structure Marker OCR" in implemented_specs
    assert "Q99. Page Worker Chunked Parallelization" in implemented_specs
    assert "Q100. OCR Page Parallelization" in implemented_specs
    assert "bounded OCR page chunk workers" in changelog
    assert "once per worker chunk instead of once per page" in changelog
    assert "context-resolvable markers avoid Tesseract calls" in changelog
    assert "dependency-audit" in implemented_specs
    assert "pdf-outline-" in implemented_specs
    assert "scripts/run_preset_eval.py" in implemented_specs
    assert "--gates preset-eval" in implemented_specs
    assert "Q44. Domain Technical Table Coverage Expansion" in implemented_specs
    assert "Q47. Local Technical Corpus Evidence Pack" in implemented_specs
    assert "Q48. Corpus Evidence Signature Analysis Report" in implemented_specs
    assert "Q49. Appendix Clause Requirement Fixture Expansion" in implemented_specs
    assert "Q50. Captionless Diagram Diagnostics Hardening" in implemented_specs
    assert "Q51. Evidence Pack History Comparison Gate" in implemented_specs
    assert "Q52. Quality Document And Schema History Contract" in implemented_specs
    assert "Q53. Minimal Desktop GUI Wrapper" in implemented_specs
    assert "Q54. GUI Runtime And Install Diagnostics" in implemented_specs
    assert "Q55. GUI Conversion Result Review UX" in implemented_specs
    assert "Q56. GUI Batch Operation Controls" in implemented_specs
    assert "Q57. Non-Developer GUI Distribution Guide" in implemented_specs
    assert "Q58. GUI Smoke And Contract Test Expansion" in implemented_specs
    assert "Q59. GUI User Guide And Help Entry" in implemented_specs
    assert "Q60. GUI Practical UX And Distribution Hardening" in implemented_specs
    assert "Q61. GUI Localization, Presets, And Progress Percent" in implemented_specs
    assert "Q62. GUI Smoke Evidence And Layout Guardrails" in implemented_specs
    assert "Q63. GUI Backlog Rollover And Forward Specs" in implemented_specs
    assert "Q64. Responsive GUI Layout And Accessibility Guardrails" in implemented_specs
    assert "Q65. GUI Runtime Doctor And Packaging Compatibility Smoke" in implemented_specs
    assert "Q66. Sanitized GUI Support Bundle" in implemented_specs
    assert "Q67. GUI Expert Options And Profile Import/Export" in implemented_specs
    assert "Q68. GUI Release Gate Integration" in implemented_specs
    assert "Q69. Wheel Contents And GUI Help Resource Contract" in implemented_specs
    assert "Q70. GUI Profile And Support Bundle Failure Fixture" in implemented_specs
    assert "Q71. Quality Scorecard Refresh And Next Backlog Reassessment" in implemented_specs
    assert "Q72. Shared Batch Runner And GUI Batch Artifact Parity" in implemented_specs
    assert "Q73. GUI Incremental Corpus Options" in implemented_specs
    assert "Q74. CLI/GUI Golden Parity Gate" in implemented_specs
    assert "Q75. GUI Metrics And Page Progress Contract" in implemented_specs
    assert "Q76. CLI/GUI Performance Benchmark Report" in implemented_specs
    assert "pdf2md/batch_runner.py" in implemented_specs
    assert "previous_corpus_manifest" in implemented_specs
    assert "scripts/run_gui_cli_parity.py" in implemented_specs
    assert "gui_cli_parity_report.json" in implemented_specs
    assert "--gates gui-parity" in implemented_specs
    assert "ConversionProgressEvent" in implemented_specs
    assert "GuiPageProgress" in implemented_specs
    assert "pages_per_second" in implemented_specs
    assert "scripts/benchmark_gui_cli_parity.py" in implemented_specs
    assert "gui_cli_benchmark_report.json" in implemented_specs
    assert "--gates gui-benchmark" in implemented_specs
    assert "tests/test_gui_profiles.py" in implemented_specs
    assert "Q72+" in implemented_specs
    assert "scripts/inspect_wheel_contract.py" in implemented_specs
    assert "pdf2md/resources/GUI_USER_GUIDE.md" in implemented_specs
    assert "tests/test_gui_profiles.py" in implemented_specs
    assert "--gates gui" in implemented_specs
    assert "python -m pdf2md.gui --doctor" in implemented_specs
    assert "scripts/create_gui_support_bundle.py" in implemented_specs
    assert "build_gui_support_bundle()" in implemented_specs
    assert "pdf2md/gui_profiles.py" in implemented_specs
    assert "tests/test_gui_profiles.py" in implemented_specs
    assert "gui_profile_payload()" in implemented_specs
    assert "gui_diagnostic_report_to_dict()" in implemented_specs
    assert "format_gui_diagnostic_report()" in implemented_specs
    assert "PR #40" in implemented_specs
    assert "scripts/run_gui_smoke_evidence.py" in implemented_specs
    assert "pdf2md/gui_layout.py" in implemented_specs
    assert "tests/test_gui_layout.py" in implemented_specs
    assert "pdf2md/gui_state.py" in implemented_specs
    assert "PR #37" in implemented_specs
    assert "PR #38" in implemented_specs
    assert "pdf2md/gui_i18n.py" in implemented_specs
    assert "pdf2md/gui_presets.py" in implemented_specs
    assert "docs/MACOS_GUI_QUICKSTART.md" in implemented_specs
    assert "docs/GUI_USER_GUIDE.md" in implemented_specs
    assert "python -m pdf2md.gui" in implemented_specs
    assert "check_gui_runtime()" in implemented_specs
    assert "format_gui_summary()" in implemented_specs
    assert "gui_options_fingerprint()" in implemented_specs
    assert "schema_version" in output_schema
    assert "docs/schema/manifest.schema.json" in output_schema
    assert "docs/schema/docling_benchmark_report.schema.json" in output_schema
    assert "docs/schema/docling_artifact_comparison.schema.json" in output_schema
    assert "ocr_backend_probe_report.json" in output_schema
    assert "docs/schema/ocr_backend_probe_report.schema.json" in output_schema
    assert "figure_description_eval_report.json" in output_schema
    assert "docs/schema/figure_description_eval_report.schema.json" in output_schema
    assert 'purpose="local_figure_description_eval"' in output_schema
    assert "options.ocr_backend" in output_schema
    assert "tesseract-cli" in output_schema
    assert "OCR_RUNTIME_UNAVAILABLE" in output_schema
    assert "figure_region_ocr_accepted_region_count" in output_schema
    assert "region_ocr.text_replaced=false" in output_schema
    assert "docling_benchmark_report.json" in output_schema
    assert "docling_artifact_comparison.json" in output_schema
    assert "docling_required_not_available" in output_schema
    assert "layout_comparison_mode" in output_schema
    assert "layout_table_candidate_count" in output_schema
    assert "layout_comparable" in output_schema
    assert "text_blocks_rag.jsonl" in output_schema
    assert "semantic_units_rag.jsonl" in output_schema
    assert "requirements_rag.jsonl" in output_schema
    assert "cross_refs_rag.jsonl" in output_schema
    assert "pdf-outline-" in output_schema
    assert "pdf-list-" in output_schema
    assert "target_source_pdf_outline" in output_schema
    assert "target_source_pdf_list" in output_schema
    assert "retrieval_chunks_rag.jsonl" in output_schema
    assert "page_layout_rag.jsonl" in output_schema
    assert "figure_ocr_evidence_rag.jsonl" in output_schema
    assert "markdown_inserted=false" in output_schema
    assert "region_refs" in output_schema
    assert "caption_links" in output_schema
    assert "source_sha256" in output_schema
    assert "figure_text" in output_schema
    assert "rag_figure_text_chunks" in output_schema
    assert "figure_text_chunk_record_count" in output_schema
    assert "rag_sidecar_omitted_outputs" in output_schema
    assert "rag_sidecar_scope_omitted" in output_schema
    assert "figures_rag.jsonl" in output_schema
    assert "domain_units_rag.jsonl" in output_schema
    assert "requirement_traceability_rag.jsonl" in output_schema
    assert "technical_tables_rag.jsonl" in output_schema
    assert "corpus_manifest.json" in output_schema
    assert "corpus_diff_report.json" in output_schema
    assert "requirement_change_impact_report.json" in output_schema
    assert "local_corpus_evidence_pack.json" in output_schema
    assert "docs/schema/local_corpus_evidence_pack.schema.json" in output_schema
    assert "corpus_evidence_analysis_report.json" in output_schema
    assert "corpus_evidence_trend_report.json" in output_schema
    assert "docs/schema/corpus_evidence_analysis_report.schema.json" in output_schema
    assert "docs/schema/corpus_evidence_trend_report.schema.json" in output_schema
    assert "tables_rag.jsonl" in output_schema
    assert "actionable_warning_count" in output_schema
    assert "table_expected_fallback_count" in output_schema
    assert "table_confidence_v2" in output_schema
    assert "table_confidence_v2_buckets" in output_schema
    assert "adaptive_skipped_strategies" in output_schema
    assert "adaptive_skip_reason" in output_schema
    assert "Warning taxonomy policy" in output_schema
    assert "Advisory warnings" in output_schema
    assert "pdf2md --help" in output_schema
    assert "2026-05-15" in quality_scorecard
    assert "2026-05-16" in quality_scorecard
    assert "Q54-Q58 active backlog" in quality_scorecard
    assert "Q54. GUI Runtime And Install Diagnostics" in quality_scorecard
    assert "Q55. GUI Conversion Result Review UX" in quality_scorecard
    assert "Q56. GUI Batch Operation Controls" in quality_scorecard
    assert "Q57. Non-Developer GUI Distribution Guide" in quality_scorecard
    assert "Q58. GUI Smoke And Contract Test Expansion" in quality_scorecard
    assert "Q59. GUI User Guide And Help Entry" in quality_scorecard
    assert "Q60. GUI Practical UX And Distribution Hardening" in quality_scorecard
    assert "GUI 실사용 UX 및 배포 계획" in quality_scorecard
    assert "Q61. GUI Localization, Presets, And Progress Percent" in quality_scorecard
    assert "GUI 언어/프리셋/진행률 계획" in quality_scorecard
    assert "Q62. GUI Smoke Evidence And Layout Guardrails" in quality_scorecard
    assert "Q64. Responsive GUI Layout And Accessibility Guardrails" in quality_scorecard
    assert "Q65. GUI Runtime Doctor And Packaging Compatibility Smoke" in quality_scorecard
    assert "Q66. Sanitized GUI Support Bundle" in quality_scorecard
    assert "Q67. GUI Expert Options And Profile Import/Export" in quality_scorecard
    assert "Q68. GUI Release Gate Integration" in quality_scorecard
    assert "Q69. Wheel Contents And GUI Help Resource Contract" in quality_scorecard
    assert "Q70. GUI Profile And Support Bundle Failure Fixture" in quality_scorecard
    assert "Q71. Quality Scorecard Refresh And Next Backlog Reassessment" in quality_scorecard
    assert "GUI batch artifact parity" in quality_scorecard
    assert "GUI incremental corpus options" in quality_scorecard
    assert "GUI/CLI golden parity gate" in quality_scorecard
    assert "GUI metrics and page progress" in quality_scorecard
    assert "GUI/CLI benchmark report" in quality_scorecard
    assert "GUI/CLI parity backlog" in quality_scorecard
    assert "Q72-Q76 active backlog/spec 추가" in quality_scorecard
    assert "Q72. Shared Batch Runner And GUI Batch Artifact Parity" in quality_scorecard
    assert "Q73. GUI Incremental Corpus Options" in quality_scorecard
    assert "Q74. CLI/GUI Golden Parity Gate" in quality_scorecard
    assert "Q75. GUI Metrics And Page Progress Contract" in quality_scorecard
    assert "Q76. CLI/GUI Performance Benchmark Report" in quality_scorecard
    assert "RAG chunk/profile implementation" in quality_scorecard
    assert "98/100" in quality_scorecard
    assert "RAG chunk/profile active backlog" in quality_scorecard
    assert "Q77. RAG Sibling Chunk Merge" in quality_scorecard
    assert "Q78. RAG Chunk Relationship Metadata" in quality_scorecard
    assert "Q79. Purpose-Specific RAG Profiles" in quality_scorecard
    assert "Q84 release readiness sweep" in quality_scorecard
    assert "Q84 Release Readiness Sweep" in quality_scorecard
    assert "Q104-Q105 Docling benchmark/design closure" in quality_scorecard
    assert "Q106 GUI assetless RAG/manual domain adapter" in quality_scorecard
    assert "Q107 assetless figure visual semantics planning" in quality_scorecard
    assert "Q108 latest NVMe command set benchmark evidence path" in quality_scorecard
    assert "Q109 Docling-installed benchmark gate" in quality_scorecard
    assert "Q110 multi OCR backend runtime probe" in quality_scorecard
    assert "Q111 OCR backend adapter contract" in quality_scorecard
    assert "Q112 region OCR report-only prototype" in quality_scorecard
    assert "Q113 local-only figure description evaluation pack" in quality_scorecard
    assert "Q114 Docling layout adapter comparison mode" in quality_scorecard
    assert "latest_nvme_command_set_scorecard.md" in quality_scorecard
    assert "이미지 업로드 불가 RAG 대응" in quality_scorecard
    assert "Docling 미설치 advisory skip" in quality_scorecard
    assert "Q91 Q90 output schema contract alignment" in quality_scorecard
    assert "Q90 cross-reference target index expansion" in quality_scorecard
    assert "cross_ref_resolved_coverage=0.9923" in quality_scorecard
    assert "Q85-Q89 preset/domain evaluation hardening" in quality_scorecard
    assert "100/100" in quality_scorecard
    assert "scripts/run_gui_cli_parity.py" in quality_scorecard
    assert "gui_cli_parity_report.json" in quality_scorecard
    assert "ConversionProgressEvent" in quality_scorecard
    assert "pages_per_second" in quality_scorecard
    assert "scripts/benchmark_gui_cli_parity.py" in quality_scorecard
    assert "gui_cli_benchmark_report.json" in quality_scorecard
    assert "Q68-Q70 reassessment" in quality_scorecard
    assert "active quality backlog는 없다" in quality_scorecard
    assert "Q72+" in quality_scorecard
    assert "GUI failure fixture hardening" in quality_scorecard
    assert "다음 active backlog는 Q71" in quality_scorecard
    assert "Wheel GUI help resource contract" in quality_scorecard
    assert "다음 active backlog는 Q70-Q71" in quality_scorecard
    assert "GUI release gate integration" in quality_scorecard
    assert "다음 active backlog는 Q69-Q71" in quality_scorecard
    assert "GUI runtime doctor" in quality_scorecard
    assert "다음 active backlog는 Q66-Q67" in quality_scorecard
    assert "GUI support bundle" in quality_scorecard
    assert "다음 active backlog는 Q67" in quality_scorecard
    assert "GUI expert options/profile" in quality_scorecard
    assert "GUI 호환성 후속 명세" in quality_scorecard
    assert "GUI smoke evidence 계획" in quality_scorecard
    assert "GUI contract test 확장" in quality_scorecard
    assert "다음 active backlog는 Q55-Q58" in quality_scorecard
    assert "다음 active backlog는 Q56-Q58" in quality_scorecard
    assert "다음 active backlog는 Q57-Q58" in quality_scorecard
    assert "다음 active backlog는 Q58" in quality_scorecard
    assert "active quality backlog 없음" in quality_scorecard
    assert "active quality backlog는 없다" in quality_scorecard
    assert "97/100" in quality_scorecard
    assert "Q46. RAG Golden Query Expected Source Coverage" in quality_scorecard
    assert "Q44. Domain Technical Table Coverage Expansion" in quality_scorecard
    assert "94/100" in quality_scorecard
    assert "Q31. Local Corpus Profile Runner" in quality_scorecard
    assert "Q35. Rendered Diagram Fixture Suite" in quality_scorecard
    assert "Q48-Q52" in quality_scorecard
    assert "Q52" in quality_scorecard
    assert "Q53. Minimal Desktop GUI Wrapper" in quality_scorecard


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

    assert 'py -3.11 -m venv .venv311' in Path("docs/WINDOWS_A_TO_Z_GUIDE.md").read_text(encoding="utf-8")
    assert '[string]$PythonVersion = "3.14"' in setup_text
    assert '[string]$VenvDir = ""' in setup_text
    assert '"Python.Python.$Version"' in setup_text
    assert "Write-ManualPythonInstallHelp" in setup_text
    assert "https://www.python.org/downloads/windows/" in setup_text
    assert "Add python.exe to PATH" in setup_text
    assert '[string]$PythonVersion = "3.14"' in run_text
    assert "Test-PythonVersionMatches" in setup_text
    assert "-RecreateVenv" in run_text
    assert '"-m", "pip", "install", "-e", ".[dev]"' in setup_text
    assert '"Scripts\\python.exe"' in setup_text
    assert '"-m", "pdf2md"' in run_text
    assert '"--input-dir", $resolvedInputDir' in run_text
    assert "setup_windows_env.ps1" in run_text
    assert "powershell -ExecutionPolicy Bypass -File" in setup_bat_text
    assert "powershell -ExecutionPolicy Bypass -File" in run_bat_text
