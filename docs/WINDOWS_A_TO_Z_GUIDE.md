# Windows A-Z 설치/실행 가이드 (Python 3.14 기준)

이 문서는 **Windows 환경에서 `pdf2md`를 설치하고 실행하는 전체 절차**를 다룹니다.
대상: 처음 세팅하는 사용자

---

## 1) 빠른 시작

ZIP 배포본을 압축 해제한 뒤, 아래 두 스크립트 중 하나로 바로 시작할 수 있습니다.

환경만 먼저 준비:

```powershell
.\scripts\setup_windows_env.bat
```

폴더 내 PDF 일괄 순차 변환까지 바로 실행:

```powershell
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

PowerShell 스크립트 본체:

- `scripts\setup_windows_env.ps1`
- `scripts\run_batch_folder_windows.ps1`

기본 정책:

- 최신 안정화 검증축 `Python 3.14`를 기본 사용
- 기본 가상환경 경로는 `.venv314`
- 배치 모드는 지정 폴더 바로 아래 PDF만 처리
- 결과는 입력 폴더 내부 `output\` 아래에 생성

---

## 2) 사전 준비

필수:

- Windows 10/11
- PowerShell
- Python 3.14.x

선택:

- Git
  - `git clone`, `git pull` 같은 저장소 동기화 흐름에서만 필요
  - ZIP 배포본 + 원클릭 스크립트 경로에서는 필수가 아님
- Tesseract OCR
  - OCR 기능 사용 시 필요

---

## 3) Python 3.14 설치

1. [Python 3.14 다운로드](https://www.python.org/downloads/windows/)
2. 설치 시 `Add python.exe to PATH` 체크
3. 설치 확인

```powershell
python --version
pip --version
```

권장 출력 예시:

- `Python 3.14.x`

버전 정책:

- 최소 지원 버전: `Python 3.11`
- 최신 안정화 검증은 별도 최신 `Python 3.14.x` 환경에서도 권장
- 실무 검증은 `3.11`과 최신 안정화 버전을 각각 별도 가상환경으로 분리해 수행

---

## 4) 저장소 받기

### A. ZIP 배포본 사용

ZIP을 압축 해제한 뒤 작업 폴더로 이동합니다.

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
```

### B. Git으로 clone

Git 기반으로 작업하려면 아래처럼 실행합니다.

```powershell
git clone https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex.git
cd ConvertPdfToMarkdownWithCodex
```

### C. 회사 보안 환경에서 `git clone`이 막힌 경우

대체 경로:

1. 소스 ZIP 반입
2. 사내 미러/아티팩트 저장소 사용
3. 소스 ZIP + `wheelhouse` + 설치 스크립트로 구성된 릴리스 번들 사용

---

## 5) 환경 구성

수동으로 환경을 만들려면:

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
python -m pdf2md --help
```

PowerShell 실행 정책 오류가 나면:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

원클릭 스크립트 사용 시:

```powershell
.\scripts\setup_windows_env.bat
```

이 스크립트가 하는 일:

1. `py -3.14 --version` 확인
2. 없으면 `winget`으로 Python 3.14 설치 시도
3. `.venv314` 생성
4. `.venv314\Scripts\python.exe -m pip install --upgrade pip`
5. `.venv314\Scripts\python.exe -m pip install -e .[dev]`
6. `.venv314\Scripts\python.exe -m pdf2md --help` 검증

직접 PowerShell로 실행할 수도 있습니다.

```powershell
.\scripts\setup_windows_env.ps1 -PythonVersion 3.14 -VenvDir .venv314
.\scripts\setup_windows_env.ps1 -SkipWingetInstall
```

완료 후 활성화 명령:

- PowerShell: `.\.venv314\Scripts\Activate.ps1`
- CMD: `.\.venv314\Scripts\activate.bat`

---

## 6) 기본 실행

예시 입력 파일: `sample.pdf`

```powershell
python -m pdf2md .\sample.pdf
```

`-o`를 생략하면 입력 PDF와 같은 위치에 `sample_output\` 폴더가 생성됩니다.

생성 파일:

- `sample_output\document.md`
- `sample_output\text_blocks_rag.jsonl`
- `sample_output\semantic_units_rag.jsonl`
- `sample_output\requirements_rag.jsonl`
- `sample_output\cross_refs_rag.jsonl`
- `sample_output\requirement_traceability_rag.jsonl`
- `sample_output\technical_tables_rag.jsonl`
- `sample_output\retrieval_chunks_rag.jsonl`
- `sample_output\figures_rag.jsonl`
- `sample_output\manifest.json`
- `sample_output\report.json`

출력 디렉터리를 직접 지정하려면:

```powershell
python -m pdf2md .\sample.pdf -o .\output
```

비밀번호 PDF:

```powershell
python -m pdf2md .\sample.pdf -o .\output --password secret
```

강제 OCR:

```powershell
python -m pdf2md .\sample.pdf -o .\output --force-ocr
```

페이지 범위:

```powershell
python -m pdf2md .\sample.pdf -o .\output --pages 1-3,5
```

페이지 마커:

```powershell
python -m pdf2md .\sample.pdf -o .\output --keep-page-markers
python -m pdf2md .\sample.pdf -o .\output --no-page-markers
```

표 모드:

```powershell
python -m pdf2md .\sample.pdf -o .\output --table-mode auto
python -m pdf2md .\sample.pdf -o .\output --table-mode html
python -m pdf2md .\sample.pdf -o .\output --table-mode markdown
```

RAG용 표 sidecar:

```powershell
python -m pdf2md .\sample.pdf -o .\output --table-mode auto --rag-table-output both
python -m pdf2md .\sample.pdf -o .\output --rag-table-output markdown
python -m pdf2md .\sample.pdf -o .\output --rag-table-output jsonl
```

- 기본값은 `none`입니다.
- 복잡 표는 `document.md`에서 HTML fallback을 유지하고, RAG용 행 단위 데이터는 별도 파일로 생성합니다.
- `rag_tables.md`: 행 단위 Markdown
- `tables_rag.jsonl`: 행 단위 structured JSONL
- 명확한 multi-row header는 `Parent / Child` 형태로 정리되고, row label 성격의 첫 번째 열은 `stub_cells`에 기록될 수 있습니다.
- adjacent page의 같은 header 표는 확실할 때만 `continuation_group`으로 연결됩니다.
- 텍스트/semantic/requirement trace/technical table/retrieval chunk/figure sidecar는 RAG 운영용으로 기본 생성됩니다.

RAG용 도메인 adapter:

```powershell
python -m pdf2md .\sample.pdf -o .\output --domain-adapter nvme --rag-table-output jsonl
```

- 기본값은 `none`입니다.
- `nvme`, `pcie`, `ocp`, `tcg`, `customer-requirements` adapter는 명확한 표 header가 있는 command/opcode/register field/bitfield/log page/requirement/security method/security object/security authority/security field만 `domain_units_rag.jsonl`로 생성합니다.

고객 대외비 스펙을 공유 가능한 metadata로 점검해야 하면:

```powershell
python -m pdf2md .\sample.pdf -o .\output --confidential-safe-mode
```

- source filename/path를 public metadata에서 마스킹하고 `sanitized_report.json`을 생성합니다.
- 외부 LLM/embedding 호출이 없음을 `manifest.json` 옵션에 기록합니다.

이미지 모드:

```powershell
python -m pdf2md .\sample.pdf -o .\output --image-mode referenced
```

보수적 품질 개선 옵션:

```powershell
python -m pdf2md .\sample.pdf -o .\output --remove-header-footer
python -m pdf2md .\sample.pdf -o .\output --dedupe-images
python -m pdf2md .\sample.pdf -o .\output --repair-hyphenation
python -m pdf2md .\sample.pdf -o .\output --figure-crop-fallback
```

- `--remove-header-footer`: 여러 페이지의 상단/하단 margin에서 반복되는 header/footer 라인만 제거합니다.
- `--dedupe-images`: 같은 `sha256` 이미지는 첫 번째 파일만 저장하고 이후 이미지는 같은 상대경로를 참조합니다.
- `--repair-hyphenation`: 명확한 줄바꿈 하이픈만 opt-in으로 복구합니다.
- `--figure-crop-fallback`: embedded image가 없고 확실한 figure caption이 있는 경우에만 crop fallback을 시도합니다.

로그 보기:

```powershell
python -m pdf2md .\sample.pdf -o .\output --verbose
python -m pdf2md .\sample.pdf -o .\output --debug
```

`--debug` 사용 시 `output\debug\` 아래에 page별 raw lines, ordered lines, normalized lines, table candidates, image candidates JSON이 생성됩니다.

---

## 7) 폴더 내 PDF 일괄 순차 변환

예시 입력 폴더: `.\pdfs`

```powershell
python -m pdf2md --input-dir .\pdfs
```

배치 모드 결과는 입력 폴더 내부 `output` 아래에 생성됩니다.

예:

- `pdfs\output\alpha\alpha.md`
- `pdfs\output\alpha\alpha_manifest.json`
- `pdfs\output\alpha\alpha_report.json`
- `pdfs\output\alpha\alpha_assets\images\...`
- `pdfs\output\batch_report.json`
- `pdfs\output\corpus_manifest.json`
- `pdfs\output\corpus_diff_report.json` (`--previous-corpus-manifest` 사용 시)
- `pdfs\output\requirement_change_impact_report.json` (`--previous-corpus-manifest` 사용 시)

배치 모드 주의사항:

- 대상은 지정 폴더 바로 아래 PDF 파일만 포함합니다.
- 배치 모드에서는 `-o/--output-dir` 을 사용하지 않습니다.
- PDF가 없는 폴더는 에러 처리됩니다.
- 같은 파일 stem을 가진 PDF가 둘 이상 있으면 충돌 방지를 위해 에러 처리됩니다.

기존 핵심 산출물이 이미 있는 문서를 건너뛰려면:

```powershell
python -m pdf2md --input-dir .\pdfs --skip-existing
```

이전 corpus manifest와 비교해 재색인/요구사항 변경 범위를 찾으려면:

```powershell
python -m pdf2md --input-dir .\pdfs_v2 --previous-corpus-manifest .\pdfs_v1\output\corpus_manifest.json
```

- `corpus_diff_report.json`: PDF 단위 `added`, `changed`, `unchanged`, `removed`
- `requirement_change_impact_report.json`: requirement trace 단위 `added`, `changed`, `removed`와 원문 `source_refs`

이전 corpus와 PDF SHA-256이 동일한 문서는 현재 출력 폴더가 비어 있을 때 이전 산출물을 재사용할 수 있습니다.

```powershell
python -m pdf2md --input-dir .\pdfs_v2 --previous-corpus-manifest .\pdfs_v1\output\corpus_manifest.json --reuse-unchanged
python scripts\build_requirement_impact_review_pack.py --impact-report .\pdfs_v2\output\requirement_change_impact_report.json
```

`batch_report.json`에서 확인할 핵심 값:

- 문서별 상태: `success`, `partial_success`, `failed`, `skipped`
- 문서별 출력 경로
- 문서별 종료 코드
- 문서별 `warning_count`, `table_count`, `image_count`, `used_ocr`, `skipped`
- `corpus_manifest.json`의 문서별 `doc_id`, `source_sha256`, `selected_pages`, RAG sidecar file map

`--skip-existing`를 사용하면 다시 처리하지 않은 문서는 `status == "skipped"` 와 `skipped == true`로 기록됩니다.

원클릭 배치 스크립트:

```powershell
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

PowerShell 본체 직접 실행:

```powershell
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs
```

예시 옵션:

```powershell
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -SkipExisting
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -TableMode html -ImageMode referenced
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -Pages 1-3,5 -NoPageMarkers
```

품질 개선 옵션을 배치 모드에서 직접 쓰려면 CLI를 사용합니다.

```powershell
python -m pdf2md --input-dir .\pdfs --remove-header-footer --dedupe-images
```

---

## 8) OCR 사용

`--force-ocr` 또는 텍스트 없는 페이지 OCR을 사용하려면 Tesseract가 필요합니다.

1. Windows용 Tesseract 설치
2. 설치 경로를 PATH에 추가
3. 확인

```powershell
tesseract --version
```

정상 출력되면 OCR 기능 사용 가능

OCR 언어 데이터가 설치되어 있으면 언어를 지정할 수 있습니다.

```powershell
python scripts\check_ocr_runtime.py --ocr-lang kor+eng
python -m pdf2md .\sample.pdf -o .\output --force-ocr --ocr-lang kor+eng
```

---

## 9) 심화 운영 점검 포인트

`manifest.json`에서 확인할 항목:

- `schema_version`
- `options.rag_table_output`
- `options.rag_text_blocks_output`
- `options.rag_text_blocks_jsonl_filename`
- `options.semantic_layer_output`
- `options.semantic_units_jsonl_filename`
- `options.requirements_jsonl_filename`
- `options.cross_refs_jsonl_filename`
- `options.requirement_traceability_jsonl_filename`
- `options.technical_tables_jsonl_filename`
- `options.retrieval_chunks_jsonl_filename`
- `options.figures_rag_jsonl_filename`
- `options.domain_adapter`
- `options.domain_units_jsonl_filename`
- `options.confidential_safe_mode`
- `options.local_only_processing`
- `options.ocr_lang`
- `options.repair_hyphenation`
- `options.figure_crop_fallback`
- `images[].alt_text`
- `images[].caption_text`, `caption_source`
- figure crop fallback 사용 시 `images[].source`, `caption_confidence`, `crop_reason`, `crop_content_ratio`, `crop_rejected_reason`
- 이미지 중복 제거 사용 시 `images[].dedupe_of`
- `excluded_images[].classification`
- `excluded_images[].recovered_text`
- `excluded_images[].ocr_candidates`
- `excluded_images[].recovery_strategy`
- `excluded_images[].context_validated`

`report.json`에서 확인할 항목:

- `schema_version`
- `page_results[].status`
- `page_results[].reading_order_strategy`
- `page_results[].column_count_estimate`
- `page_results[].text_layer_char_count`
- `page_results[].ocr_attempted`, `ocr_reason`, `ocr_runtime_available`
- `page_results[].header_footer_suppressed_count`
- `summary.page_status_counts`
- `summary.table_fallback_count`
- `summary.table_fallbacks`
- `summary.table_mode_requested`
- `summary.stage_durations_ms`
- `summary.pdf_open_count`
- `summary.pages_per_second`
- `summary.page_cache_hits`
- `summary.page_cache_misses`
- `summary.text_line_extract_count`
- `summary.heading_count`
- `summary.list_item_count`
- `summary.code_block_count`
- `summary.hyphenation_repair_count`
- `summary.rag_text_block_record_count`
- `summary.rag_text_block_file_count`
- `summary.semantic_unit_record_count`
- `summary.semantic_unit_file_count`
- `summary.requirement_record_count`
- `summary.requirement_file_count`
- `summary.cross_ref_record_count`
- `summary.cross_ref_file_count`
- `summary.semantic_low_confidence_count`
- `summary.unresolved_cross_ref_count`
- `summary.normative_requirement_count`
- `summary.retrieval_chunk_record_count`
- `summary.retrieval_chunk_file_count`
- `summary.figure_rag_record_count`
- `summary.figure_rag_file_count`
- `summary.domain_unit_record_count`
- `summary.domain_unit_file_count`
- `summary.requirement_traceability_record_count`
- `summary.requirement_traceability_file_count`
- `summary.technical_table_record_count`
- `summary.technical_table_file_count`
- `summary.retrieval_chunk_max_token_estimate`
- `summary.retrieval_chunk_average_token_estimate`
- `summary.retrieval_chunk_over_target_count`
- `summary.retrieval_chunk_duplicate_source_ref_count`
- `summary.confidential_safe_mode`
- `summary.font_heading_candidate_count`
- `summary.footnote_candidate_count`
- `summary.structure_low_confidence_count`

출력 schema 안정성 정책과 RAG sidecar field 계약은 `docs\OUTPUT_SCHEMA.md`에서 확인합니다.
Machine-readable schema는 `docs\schema\manifest.schema.json`, `docs\schema\report.schema.json`, `docs\schema\batch_report.schema.json`, `docs\schema\corpus_manifest.schema.json`, `docs\schema\corpus_diff_report.schema.json`, `docs\schema\requirement_change_impact_report.schema.json`에 있으며 `python scripts\export_output_schema.py --check`로 검증합니다.
- `summary.rag_table_output`
- `summary.rag_table_record_count`
- `summary.rag_table_file_count`
- `summary.table_fallback_reason_counts`
- `summary.table_low_quality_count`
- `summary.table_caption_linked_count`
- `summary.table_markdown_forced_count`
- `summary.table_html_forced_count`
- `summary.structure_marker_recovered_count`
- `summary.structure_marker_recovered_exact_count`
- `summary.structure_marker_recovered_context_count`
- `summary.structure_marker_suppressed_count`

표 품질을 볼 때는 `summary.table_quality[]`의 optional 진단 필드도 같이 확인하세요.
주요 필드는 `header_depth`, `header_confidence`, `stub_column_count`,
`footnote_row_count`, `merged_cell_suspected`, `rag_header_strategy`입니다.

구조 인덱스가 중요한 기술 문서 운영 팁:

- tiny 좌측 여백 구조 마커를 가능한 경우 `2.2.1`, `4.1.7` 같은 텍스트로 복구합니다.
- 문서 품질 점검 시 표 fallback뿐 아니라 구조 마커 복구도 같이 확인하는 것이 좋습니다.
- 확인 위치:
  - `document.md`
  - `text_blocks_rag.jsonl`
  - `semantic_units_rag.jsonl`
  - `requirements_rag.jsonl`
  - `cross_refs_rag.jsonl`
  - `requirement_traceability_rag.jsonl`
  - `technical_tables_rag.jsonl`
  - `retrieval_chunks_rag.jsonl`
  - `figures_rag.jsonl`
  - `manifest.json`
  - `report.json`

Debug 산출물 확인 위치:

- `output\debug\page-0001-raw-lines.json`
- `output\debug\page-0001-ordered-lines.json`
- `output\debug\page-0001-normalized-lines.json`
- `output\debug\page-0001-table-candidates.json`
- `output\debug\page-0001-image-candidates.json`

로컬 corpus 평가와 benchmark:

```powershell
python scripts\run_corpus_eval.py --input-dir pdf --output-dir pdf\eval_output
python scripts\run_corpus_eval.py --input-dir pdf --output-dir pdf\eval_output --baseline-report pdf\baseline\corpus_eval_report.json --max-partial-rate 0.1 --max-low-quality-table-rate 0.05 --min-pages-per-second 1.0 --fail-on-regression
python scripts\benchmark_conversion.py --output-dir .\benchmark_output --page-counts 10,50,100
python scripts\benchmark_conversion.py --output-dir .\benchmark_output --page-counts 10,50,100 --baseline-report .\benchmark_baseline\benchmark_report.json --max-duration-regression 0.2 --max-memory-regression 0.2 --min-pages-per-second 1.0 --fail-on-regression
python scripts\run_rag_eval.py --output-dir .\output --eval-set .\rag_eval_queries.json --top-k 5
python scripts\run_rag_eval.py --output-dir .\output --eval-set .\rag_eval_queries.json --top-k 5 --min-expected-source-coverage 0.9 --min-requirement-coverage 0.9 --min-table-field-coverage 0.85 --min-cross-ref-resolved-coverage 0.8 --max-chunk-token-p95 512 --max-conversion-duration-ms 10000 --fail-on-threshold
python scripts\run_rag_eval.py --output-dir .\output --eval-set .\rag_eval_queries.json --calibration-profile docs\rag_calibration_profile.example.json --fail-on-threshold
python scripts\validate_ssd_rag_contract.py --output-dir .\output --ssd-agent-domain HIL --ssd-agent-spec-type TCG --domain-adapter tcg
python scripts\run_ssd_corpus_profile.py --profile .\local_ssd_corpus_profile.json --fail-on-error
python scripts\run_ssd_corpus_profile.py --profile .\local_ssd_corpus_profile.json --fail-on-error --evidence-pack
python scripts\build_requirement_impact_review_pack.py --impact-report .\output\requirement_change_impact_report.json
python scripts\run_release_gates.py --output-dir .\release_gate_output --gates ocr,corpus,benchmark,schema,packaging --corpus-input-dir pdf --corpus-baseline-report pdf\baseline\corpus_eval_report.json --benchmark-baseline-report .\benchmark_baseline\benchmark_report.json
python scripts\run_release_gates.py --output-dir .\release_gate_rag --gates rag --rag-output-dir .\output --rag-eval-set .\rag_eval_queries.json --rag-min-expected-source-coverage 0.9 --rag-min-requirement-coverage 0.9 --rag-min-table-field-coverage 0.85 --rag-min-cross-ref-resolved-coverage 0.8
```

- 실제 PDF는 `pdf\` 같은 로컬 디렉터리에만 두고 repo에 커밋하지 않습니다.
- `corpus_eval_report.json`: success/partial 집계, fallback reason, suppressed line, low quality table, pages/sec, pdf open count, text line extract count, regression summary
- `benchmark_report.json`: duration, stage duration, pages/sec, pdf open count, text line extract count, peak memory, regression summary
- `rag_eval_report.json`: hit@k, MRR, expected source coverage, requirement/table-field/cross-ref coverage, chunk token 분포, query별 retrieved chunk/source id와 missing expected source id
- `ssd_rag_contract_report.json`: `retrieval_chunks_rag.jsonl`이 SSD 에이전트 `RagChunk/RagCitation` 계약으로 매핑 가능한지 검사한 결과. TCG는 `HIL/TCG` first-class spec_type으로 검증합니다.
- `ssd_corpus_profile_report.json`: local-only NVMe/PCIe/OCP/TCG profile 변환, SSD 계약 검증, 선택적 RAG eval aggregate 집계
- `local_corpus_evidence_pack.json`: 비공개 corpus 실패 패턴을 raw path, command, filename, query text 없이 공유하기 위한 redacted signature 집계
- `requirement_impact_review_pack.json` / `.md`: requirement change impact를 리뷰어/AI Agent가 바로 확인할 수 있게 정리한 provenance 중심 요약
- `release_gate_report.json`: OCR preflight, corpus quality gate, benchmark performance gate, optional RAG calibration gate, schema check, packaging smoke command/status summary
- benchmark는 수동/릴리스 전 검증용이며 기본 테스트에 포함하지 않습니다.
- 패키징 smoke는 릴리스 전에 `python -m build`, wheel 설치 후 `python -m pdf2md --help`, `pdf2md --help` 순서로 확인합니다.
- GitHub Actions CI는 PR/push마다 `python -m pytest`와 `python -m pdf2md --help`를 실행합니다.
- 향후 작업 backlog는 `docs\NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 새 작업만 남기고, 완료된 항목은 제거합니다.
- active 개발 명세는 `docs\QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에 작성하고, 완료된 명세는 `docs\QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관합니다.

---

## 10) 테스트 실행

```powershell
pytest -q -p no:cacheprovider
```

또는

```powershell
python -m pytest -q -p no:cacheprovider
```

### 10-1) Python 버전별 검증 권장 절차

최소 지원 버전 `3.11`:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m pytest -q -p no:cacheprovider
python -m pdf2md --help
deactivate
```

최신 안정화 버전 `3.14`:

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m pytest -q -p no:cacheprovider
python -m pdf2md --help
deactivate
```

---

## 11) 종료 코드 의미

- `0`: 성공
- `1`: 치명적 실패
- `2`: 부분 성공

`2`는 실패가 아니라, 일부 warning이나 fallback이 포함된 정상 실행일 수 있습니다.

---

## 12) 트러블슈팅

### A. `python` 명령이 안 잡힘

- Python 설치 시 PATH 체크 누락 가능
- 새 PowerShell 재실행
- `py -3.11 --version`, `py -3.14 --version`으로 확인

### B. `ModuleNotFoundError`

- 가상환경 미활성화 가능
- 아래 순서 재실행

```powershell
.\.venv314\Scripts\Activate.ps1
pip install -e .[dev]
```

### C. OCR warning (`OCR_RUNTIME_UNAVAILABLE`)

- Tesseract 미설치 또는 PATH 미설정
- `tesseract --version` 먼저 확인

### D. 이미지가 없다는 warning (`IMAGE_NOT_FOUND`)

- PDF에 embedded 이미지가 없으면 정상 경고일 수 있음
- 스캔 PDF라도 이미지 객체가 표준 임베드 형식이 아닐 수 있음

### E. `embedded` 또는 `placeholder` 모드인데 `assets\images`가 비어 있음

- `referenced` 모드에서만 실제 이미지 파일을 저장합니다.
- `embedded`는 Markdown 내부 data URI, `placeholder`는 comment만 남깁니다.

### F. 표가 기대보다 많거나 적게 추출됨

- `report.json > summary.table_*`와 `warnings[].details.reasons`를 우선 확인하세요.
- `markdown` 모드에서는 복잡 표도 Markdown으로 강제되므로 일부 구조 손실이 있을 수 있습니다.

### G. 권한 문제

- 회사 보안 정책으로 스크립트 실행이 제한될 수 있습니다.
- PowerShell 정책 또는 보안 솔루션 정책을 확인하세요.

---

## 13) 업데이트 방법

Git 기반 작업 시:

```powershell
git pull origin main
.\.venv314\Scripts\Activate.ps1
pip install -e .[dev]
```

ZIP 배포본 사용 시:

- 새 ZIP을 다시 받아 교체한 뒤
- `.\scripts\setup_windows_env.bat` 또는 수동 설치 절차를 재실행

---

## 14) `git clone` 없이 실행하는 실전 예시

### A. 소스 ZIP만 있는 경우(인터넷 가능 환경)

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
.\scripts\setup_windows_env.bat
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

배치 결과 예시:

- `pdfs\output\alpha\alpha.md`
- `pdfs\output\alpha\alpha_manifest.json`
- `pdfs\output\alpha\alpha_report.json`
- `pdfs\output\batch_report.json`
- `pdfs\output\corpus_manifest.json`

단일 PDF만 빠르게 실행하고 싶다면:

```powershell
.\.venv314\Scripts\python.exe -m pdf2md .\sample.pdf -o .\output
```

### B. 완전 오프라인 환경(의존성 wheel 반입)

사전 준비:

- 프로젝트 소스 ZIP
- `wheelhouse` 폴더

사내 PC 실행:

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
pip install --no-index --find-links .\wheelhouse -e .
python -m pdf2md .\sample.pdf -o .\output
```
