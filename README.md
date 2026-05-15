# PDF to Markdown Converter

PDF 문서를 **신뢰성 있게 Markdown으로 변환**하기 위한 CLI/라이브러리 프로젝트입니다.

이 프로젝트의 1차 목표는 보기 좋은 재구성이 아니라, **원문 보존성과 재처리 가능성**이 높은 Markdown 산출물을 만드는 것입니다.

핵심 원칙은 아래 3가지입니다.

- **텍스트는 그대로 유지**: 요약, 교정, 재서술 없이 원문 중심으로 추출
- **테이블은 표로 유지**: 단순 표는 GFM, 복잡 표는 HTML fallback
- **이미지는 외부 파일 참조가 기본**: Markdown은 상대경로 링크, 이미지 파일은 assets에 저장

---

## 1. 프로젝트 목표

### 목표

- 단일 PDF 또는 폴더 내 여러 PDF를 입력받아 Markdown, asset, report 산출물을 생성
- 디지털 PDF와 스캔 PDF(OCR 필요) 모두 처리
- 본문 순서, 제목, 문단, 목록, 표, 이미지 위치를 가능한 범위에서 안정적으로 복원
- 동일 입력 + 동일 옵션이면 동일 출력이 나오도록 deterministic 설계
- 우선 지원 인터페이스는 CLI이며, 내부 파이프라인은 라이브러리처럼 재사용 가능하도록 유지
- `manifest.json`, `report.json`, `batch_report.json`, `corpus_manifest.json`으로 재처리 가능한 메타데이터 제공

### 비목표

- DTP/WYSIWYG 수준의 완벽한 레이아웃 복원
- 모든 복잡 문서를 완벽하게 시각적으로 재현
- 기본 동작에서 VLM 기반 이미지 설명 생성
- 차트/다이어그램의 의미 해석이나 데이터 재구성

---

## 2. 참조 문서

구현 우선순위는 아래 순서를 따릅니다.

1. 사용자 직접 지시
2. `PRD_pdf_to_markdown_converter.md`
3. `tasks.md`
4. `AGENTS.md`
5. 본 `README.md`

이 저장소를 처음 여는 경우 아래 순서로 읽는 것을 권장합니다.

1. `README.md`
2. `PRD_pdf_to_markdown_converter.md`
3. `tasks.md`
4. `AGENTS.md`

---

## 3. 현재 제공 기능

### 텍스트

- `pdfplumber` 중심으로 텍스트를 추출합니다.
- 공백 정리는 최소화하되 의미 손실은 피합니다.
- OCR 결과도 의미를 바꾸는 후처리를 하지 않습니다.
- RAG 등록을 기본 운영 경로로 보고 `text_blocks_rag.jsonl`, semantic sidecar 3종, `requirement_traceability_rag.jsonl`, `technical_tables_rag.jsonl`, `retrieval_chunks_rag.jsonl`, `figures_rag.jsonl`을 기본 생성합니다.

### 테이블

- 단순 표는 GFM pipe table로 출력합니다.
- 복잡 표는 HTML fallback을 우선합니다.
- `--table-mode auto|html|markdown`을 지원합니다.
- `html-only`, `gfm-only`는 legacy compatibility mode로 유지됩니다.
- RAG 등록용으로 `document.md` 정책을 바꾸지 않고 `rag_tables.md`, `tables_rag.jsonl` sidecar를 opt-in으로 생성할 수 있습니다.

### 이미지

- 기본 모드는 `referenced`입니다.
- `assets/images/` 아래에 이미지 파일을 저장하고 Markdown 본문에서는 상대경로로 연결합니다.
- `embedded`, `placeholder`도 선택적으로 지원합니다.
- 인접 캡션이 확실한 경우 `caption_text`, `caption_source`를 metadata에 기록합니다.
- RAG 운영을 위해 이미지/도표 provenance를 `figures_rag.jsonl`에 별도로 기록합니다.

### OCR

- 스캔 PDF 또는 텍스트가 거의 없는 페이지에서 OCR을 적용합니다.
- `--force-ocr` 옵션을 지원합니다.
- OCR 경로는 `pytesseract + pypdfium2`를 사용합니다.

### 실패 처리

- partial success를 우선합니다.
- 특정 페이지/표/이미지 실패로 전체 문서를 중단하지 않습니다.
- 실패와 경고는 `report.json`과 Markdown comment로 기록합니다.

---

## 4. 기술 스택

### 핵심

- Python 3.11+
- `pypdf`
- `pdfplumber`
- `pydantic`
- `argparse`

### OCR / 이미지 처리

- `pytesseract`
- `pypdfium2`
- `Pillow`

### 테스트

- `pytest`
- golden output 비교 테스트
- CLI smoke test

### Python 지원 정책

- 공식 지원 범위: `Python 3.11+`
- 최소 지원 검증축: `Python 3.11`
- 최신 안정화 검증축: 현재 시점의 최신 안정화 `Python 3.14`
- 로컬 기본 `python3`가 더 낮은 버전을 가리키는 경우, 버전 명시 실행기 또는 venv의 `python`을 사용

---

## 5. 현재 프로젝트 구조

```text
pdf2md/
  __init__.py
  __main__.py
  cli.py
  config.py
  constants.py
  models.py
  pipeline.py
  reporting.py
  extractors/
    images.py
    ocr.py
    structure_normalizer.py
    tables.py
    text.py
  serializers/
    manifest.py
    markdown.py
    rag_chunks.py
    rag_domain_adapters.py
    rag_figures.py
    rag_requirements.py
    rag_semantics.py
    rag_tables.py
    rag_technical_tables.py
    rag_text_blocks.py
    report.py
  utils/
    io.py
    logging.py
    page_range.py
    pdf.py
    structure.py
tests/
  fixtures/
  ...
scripts/
  validate_python_matrix.sh
  setup_windows_env.ps1
  setup_windows_env.bat
  run_batch_folder_windows.ps1
  run_batch_folder_windows.bat
  benchmark_conversion.py
  check_ocr_runtime.py
  export_output_schema.py
  run_corpus_eval.py
  run_rag_eval.py
  run_release_gates.py
  run_ssd_corpus_profile.py
  validate_ssd_rag_contract.py
```

---

## 6. 설치 가이드

### Python 환경 생성

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
```

일부 macOS/Linux 환경에서는 `python` 대신 `python3`만 제공될 수 있습니다.
그 경우 아래처럼 실행하세요.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
```

지원 버전을 명확히 맞추려면 아래처럼 실행기를 고정하는 것을 권장합니다.

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -U pip
```

### 패키지 설치

```bash
pip install -e .[dev]
```

### 시스템 의존성 예시

macOS:

```bash
brew install tesseract
```

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

`pypdfium2`는 Python 패키지로 설치되며, OCR을 실제로 사용하려면 시스템에 Tesseract가 있어야 합니다.

### Windows 설치/실행 가이드

- Windows 전용 상세 문서: [docs/WINDOWS_A_TO_Z_GUIDE.md](/Users/mankiw/VS_Project/ConvertPdfToMarkdown/docs/WINDOWS_A_TO_Z_GUIDE.md)
- 회사 보안 환경(온라인 설치 제한, `git clone` 제한) 대응 절차 포함
- ZIP 배포본 기준 원클릭 환경 구성: `scripts\setup_windows_env.ps1`, `scripts\setup_windows_env.bat`
- ZIP 배포본 기준 폴더 배치 변환: `scripts\run_batch_folder_windows.ps1`, `scripts\run_batch_folder_windows.bat`

---

## 7. CLI 사용 예시

### 가장 기본 실행

macOS/Linux 예시:

```bash
python3 -m pdf2md input.pdf
```

위 명령은 입력 PDF와 같은 디렉터리에 `<pdf_stem>_output/` 폴더를 기본 생성합니다.

엔트리포인트가 설치되어 있으면 아래처럼 실행해도 됩니다.

```bash
pdf2md input.pdf
```

출력 폴더를 직접 지정하려면:

```bash
python3 -m pdf2md input.pdf -o output/
```

### 폴더 내 PDF 일괄 순차 변환

```bash
python3 -m pdf2md --input-dir ./pdfs
```

배치 모드에서는 지정한 입력 폴더 내부에 `output/` 폴더를 만들고, 각 PDF마다 아래 구조로 결과를 생성합니다.

- `./pdfs/output/<pdf_stem>/<pdf_stem>.md`
- `./pdfs/output/<pdf_stem>/<pdf_stem>_manifest.json`
- `./pdfs/output/<pdf_stem>/<pdf_stem>_report.json`
- `./pdfs/output/<pdf_stem>/<pdf_stem>_assets/images/...`
- `./pdfs/output/batch_report.json`
- `./pdfs/output/corpus_manifest.json`
- `./pdfs/output/corpus_diff_report.json` # `--previous-corpus-manifest` 사용 시
- `./pdfs/output/requirement_change_impact_report.json` # `--previous-corpus-manifest` 사용 시

배치 모드 주의사항:

- 입력 대상은 지정 폴더 바로 아래의 PDF 파일만 포함합니다.
- 배치 모드에서는 `-o/--output-dir` 을 사용하지 않습니다.
- PDF가 하나도 없으면 에러로 종료합니다.
- 같은 stem을 가진 PDF가 둘 이상 있으면 충돌 방지를 위해 에러로 종료합니다.

### 일부 페이지만 변환

```bash
python3 -m pdf2md input.pdf -o output/ --pages 1-3,5,7-9
```

### 비밀번호 PDF 변환

```bash
python3 -m pdf2md input.pdf -o output/ --password secret
```

### 강제 OCR

```bash
python3 -m pdf2md input.pdf -o output/ --force-ocr
```

### 이미지 placeholder 모드

```bash
python3 -m pdf2md input.pdf -o output/ --image-mode placeholder
```

### 테이블을 HTML 우선으로 출력

```bash
python3 -m pdf2md input.pdf -o output/ --table-mode html
```

### 테이블을 Markdown으로 강제 출력

```bash
python3 -m pdf2md input.pdf -o output/ --table-mode markdown
```

### RAG용 표 sidecar 출력

```bash
python3 -m pdf2md input.pdf -o output/ --rag-table-output both
python3 -m pdf2md input.pdf -o output/ --rag-table-output markdown
python3 -m pdf2md input.pdf -o output/ --rag-table-output jsonl
```

- 기본값은 `none`입니다.
- `document.md`는 기존 정책을 유지합니다: 단순 표는 GFM, 복잡 표는 HTML fallback.
- `rag_tables.md`는 행 단위 Markdown, `tables_rag.jsonl`은 stable `table_id`/`table_row_id`를 포함한 행 단위 structured JSONL입니다.
- 텍스트, 스펙 semantic, retrieval chunk, figure sidecar는 별도 옵션 없이 항상 생성됩니다.

### RAG용 도메인 adapter

```bash
python3 -m pdf2md input.pdf -o output/ --domain-adapter nvme --rag-table-output jsonl
```

- 기본값은 `none`이며, 도메인 heuristic은 기본 변환 로직에 섞지 않습니다.
- `nvme`, `pcie`, `ocp`, `tcg`, `customer-requirements` adapter는 표 provenance가 명확한 command/opcode/register field/bitfield/log page/requirement/security method/security object/security authority/security field 행만 `domain_units_rag.jsonl`로 생성합니다.
- 생성된 domain unit은 `retrieval_chunks_rag.jsonl`에도 provenance와 함께 포함됩니다.

### 고객 대외비 스펙 안전 모드

```bash
python3 -m pdf2md input.pdf -o output/ --confidential-safe-mode
```

- 외부 LLM/embedding 호출이 없음을 `manifest.json` 옵션에 명시합니다.
- `manifest.json`의 source filename을 마스킹하고 `sanitized_report.json`을 추가 생성합니다.
- batch/corpus metadata에서 공유용 파일 경로는 가능한 범위에서 filename 또는 document id로 축약합니다.

### 페이지 마커 제어

```bash
python3 -m pdf2md input.pdf -o output/ --keep-page-markers
python3 -m pdf2md input.pdf -o output/ --no-page-markers
```

### 보수적 품질 개선 옵션

```bash
python3 -m pdf2md input.pdf -o output/ --remove-header-footer
python3 -m pdf2md input.pdf -o output/ --dedupe-images
python3 -m pdf2md input.pdf -o output/ --repair-hyphenation
python3 -m pdf2md input.pdf -o output/ --figure-crop-fallback
```

- `--remove-header-footer`: 여러 페이지의 margin 영역에서 반복되는 header/footer 라인만 제거합니다.
- `--dedupe-images`: 동일 `sha256` 이미지는 첫 파일만 저장하고 이후 asset은 같은 상대경로를 참조합니다.
- `--repair-hyphenation`: 명확한 줄바꿈 하이픈만 opt-in으로 복구합니다.
- `--figure-crop-fallback`: embedded image가 없고 확실한 figure caption이 있는 페이지에서만 crop fallback을 시도합니다.

### OCR 언어 지정

```bash
python3 scripts/check_ocr_runtime.py --ocr-lang kor+eng
python3 -m pdf2md input.pdf -o output/ --force-ocr --ocr-lang kor+eng
```

- 기본값은 `eng`입니다.
- 변환 전에 `scripts/check_ocr_runtime.py`로 Tesseract 실행 파일, Python OCR 패키지, `kor+eng` 언어팩 설치 여부를 점검할 수 있습니다.
- OCR runtime이 없거나 confidence가 낮으면 결과를 정답처럼 숨기지 않고 `report.json` warning과 page diagnostics에 남깁니다.

### 실행 로그 보기

```bash
pdf2md input.pdf -o output/ --verbose
pdf2md input.pdf -o output/ --debug
```

`--debug`를 사용하면 일반 산출물과 별도로 `debug/` 디렉터리에 page별 intermediate JSON이 생성됩니다.
예: raw lines, ordered lines, normalized lines, table candidates, image candidates.

### 기존 배치 산출물이 있으면 건너뛰기

```bash
python3 -m pdf2md --input-dir ./pdfs --skip-existing
```

### 이전 corpus와 비교해 재색인/요구사항 변경 범위 찾기

```bash
python3 -m pdf2md --input-dir ./pdfs_v2 --previous-corpus-manifest ./pdfs_v1/output/corpus_manifest.json
```

- `corpus_diff_report.json`: PDF 단위 `added`, `changed`, `unchanged`, `removed`를 기록합니다.
- `requirement_change_impact_report.json`: `requirement_traceability_rag.jsonl` 기준 requirement 단위 `added`, `changed`, `removed`와 원문 `source_refs`를 기록합니다.
- 문장 요약/재서술 없이 diff provenance만 제공하므로 AI Agent의 영향 분석 입력으로 쓰기 좋습니다.

동일한 PDF SHA-256이 이전 corpus에 있고 현재 출력 디렉터리가 비어 있으면 이전 산출물을 재사용할 수 있습니다.

```bash
python3 -m pdf2md --input-dir ./pdfs_v2 --previous-corpus-manifest ./pdfs_v1/output/corpus_manifest.json --reuse-unchanged
python3 scripts/build_requirement_impact_review_pack.py --impact-report ./pdfs_v2/output/requirement_change_impact_report.json
```

`--reuse-unchanged`로 재사용된 문서는 `batch_report.json`과 `corpus_manifest.json`에서 `status == "skipped"`, `skipped == true`로 기록됩니다. Review pack script는 `requirement_impact_review_pack.json`과 `requirement_impact_review_pack.md`를 생성합니다.

### 실행기 표기 정책

- 이 README의 기본 예시는 macOS/Linux 기준으로 `python3 -m pdf2md`를 사용합니다.
- Windows에서는 보통 `python -m pdf2md`를 사용합니다.
- 설치형 엔트리포인트가 잡혀 있으면 `pdf2md ...`로 실행할 수 있습니다.

---

## 8. Python 버전 검증

최소 지원 버전과 최신 안정화 버전을 모두 검증하려면 아래 순서를 권장합니다.

### 최소 지원 버전 검증

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
python -m pytest
python -m pdf2md --help
deactivate
```

### 최신 안정화 버전 검증

macOS/Homebrew 예시:

```bash
brew install python@3.14
python3.14 -m venv .venv314
source .venv314/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
python -m pytest
python -m pdf2md --help
deactivate
```

반복 실행이 필요하면 아래 스크립트를 사용할 수 있습니다.

```bash
./scripts/validate_python_matrix.sh
```

Windows ZIP 배포본에서는 아래 스크립트로 동일한 목적의 환경 구성을 수행할 수 있습니다.

```powershell
.\scripts\setup_windows_env.bat
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

---

## 9. 출력 구조

단일 PDF 기본 출력 예시는 아래와 같습니다.

```text
output/
  document.md
  text_blocks_rag.jsonl # 기본 생성되는 텍스트 블록 RAG sidecar
  semantic_units_rag.jsonl # 기본 생성되는 스펙 semantic unit sidecar
  requirements_rag.jsonl   # 기본 생성되는 요구사항 filtered sidecar
  cross_refs_rag.jsonl     # 기본 생성되는 section/table/figure 참조 sidecar
  requirement_traceability_rag.jsonl # 기본 생성되는 requirement trace/conformance sidecar
  technical_tables_rag.jsonl # 기본 생성되는 register/bitfield/opcode/log page table sidecar
  retrieval_chunks_rag.jsonl # 기본 생성되는 vector DB ingest 후보 chunk
  figures_rag.jsonl       # 기본 생성되는 figure/diagram provenance sidecar
  domain_units_rag.jsonl  # --domain-adapter 사용 시
  sanitized_report.json   # --confidential-safe-mode 사용 시
  rag_tables.md          # --rag-table-output markdown|both 사용 시
  tables_rag.jsonl       # --rag-table-output jsonl|both 사용 시
  assets/
    images/
      page-0001-figure-001.png
      page-0002-figure-002.png
  debug/                 # --debug 사용 시에만 생성
    page-0001-raw-lines.json
    page-0001-ordered-lines.json
    page-0001-normalized-lines.json
    page-0001-table-candidates.json
    page-0001-image-candidates.json
  manifest.json
  report.json
```

배치 변환 출력 예시는 아래와 같습니다.

```text
pdfs/
  a.pdf
  b.pdf
  output/
    a/
      a.md
      a_manifest.json
      a_report.json
      a_assets/
        images/
    b/
      b.md
      b_manifest.json
      b_report.json
      b_assets/
        images/
    batch_report.json
    corpus_manifest.json
    corpus_diff_report.json                # --previous-corpus-manifest 사용 시
    requirement_change_impact_report.json  # --previous-corpus-manifest 사용 시
```

### `document.md`

- 최종 Markdown 본문
- 페이지 마커 옵션 지원
- 표/이미지 위치 보존 주석 포함 가능

### `manifest.json`

- 입력 파일명
- 처리 옵션
- 생성된 asset 목록
- 페이지 수 및 산출물 메타데이터
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
- 이미지별 `alt_text`
- 인접 캡션이 확실할 때만 `caption_text`, `caption_source`
- figure crop fallback 사용 시 이미지별 `source`, `caption_confidence`, `crop_reason`, `crop_content_ratio`, `crop_rejected_reason`
- 이미지 중복 제거 사용 시 `dedupe_of`
- 구조 마커 복구 메타데이터
  - `classification == "STRUCTURE_MARKER"`
  - `recovered_text`
  - `ocr_candidates`
  - `recovery_strategy`
  - `context_validated`
  - `parent_heading_index`

### `report.json`

- 처리 시간
- warning / failure
- OCR 적용 여부
- 페이지별 처리 결과 요약
- `schema_version`
- 페이지별 `status`
- 페이지별 `reading_order_strategy`, `column_count_estimate`
- 페이지별 `text_layer_char_count`, `ocr_attempted`, `ocr_reason`, `ocr_runtime_available`
- 페이지별 `header_footer_suppressed_count`
- `summary.page_status_counts`
- `summary.table_mode_requested`
- `summary.table_quality`
- `summary.table_fallback_count`
- `summary.table_fallbacks`
- `summary.table_markdown_forced_count`
- `summary.table_html_forced_count`
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
- `summary.rag_table_output`
- `summary.rag_table_record_count`
- `summary.rag_table_file_count`
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
- `summary.retrieval_chunk_max_token_estimate`
- `summary.retrieval_chunk_average_token_estimate`
- `summary.retrieval_chunk_over_target_count`
- `summary.retrieval_chunk_duplicate_source_ref_count`
- `summary.figure_rag_record_count`
- `summary.figure_rag_file_count`
- `summary.domain_unit_record_count`
- `summary.domain_unit_file_count`
- `summary.requirement_traceability_record_count`
- `summary.requirement_traceability_file_count`
- `summary.technical_table_record_count`
- `summary.technical_table_file_count`
- `summary.confidential_safe_mode`
- `summary.font_heading_candidate_count`
- `summary.footnote_candidate_count`
- `summary.structure_low_confidence_count`
- `summary.table_fallback_reason_counts`
- `summary.table_low_quality_count`
- `summary.table_caption_linked_count`
- `summary.structure_marker_recovered_count`
- `summary.structure_marker_recovered_exact_count`
- `summary.structure_marker_recovered_context_count`
- `summary.structure_marker_suppressed_count`

출력 schema 안정성 정책과 RAG sidecar field 계약은 [docs/OUTPUT_SCHEMA.md](docs/OUTPUT_SCHEMA.md)에 별도로 정리합니다.
Machine-readable schema는 `docs/schema/`에 있으며, 예를 들어 `docs/schema/manifest.schema.json`과 `docs/schema/local_corpus_evidence_pack.schema.json`을 `python scripts/export_output_schema.py --check`로 검증합니다.

`summary.table_quality[]`에는 표별 품질 진단이 기록됩니다. 복잡 표에서는
`header_depth`, `header_confidence`, `stub_column_count`, `footnote_row_count`,
`merged_cell_suspected`, `rag_header_strategy` 같은 optional 필드를 통해
HTML fallback과 RAG sidecar 생성 판단을 추적할 수 있습니다.
multi-page table continuation 후보는 `continuation_reasons`,
`continuation_rejected_reasons`, `continuation_features`로 판단 근거를 남깁니다.

### `debug/`

- `--debug` 사용 시에만 생성됩니다.
- page별 raw/ordered/normalized text line과 table/image 후보 정보를 JSON으로 저장합니다.
- 변환 결과에는 영향을 주지 않는 진단용 산출물이며, 일반 운영에서는 생략해도 됩니다.

### `batch_report.json`

- 배치 모드에서만 생성되는 집계 파일
- 처리 대상 PDF 목록
- 문서별 상태: `success`, `partial_success`, `failed`, `skipped`
- 문서별 출력 경로와 파일 경로
- 문서별 종료 코드
- 문서별 `warning_count`, `table_count`, `image_count`, `used_ocr`, `skipped`
- 전체 성공/부분성공/실패/건너뛰기 집계

### `corpus_manifest.json`

- 배치 모드에서만 생성되는 RAG corpus ingest manifest
- 문서별 `doc_id`, `source_sha256`, `selected_pages`, output file map 기록
- `text_blocks_rag`, semantic sidecar, retrieval chunk, figure sidecar 경로를 한 곳에서 추적
- 여러 PDF 스펙을 같은 vector DB corpus로 운영할 때 incremental ingest/diff의 기준으로 사용

### `corpus_diff_report.json`

- `--input-dir`와 `--previous-corpus-manifest`를 함께 사용할 때 생성됩니다.
- 이전/현재 `corpus_manifest.json`의 `doc_id`와 `source_sha256`을 비교해 `added`, `changed`, `unchanged`, `removed`를 기록합니다.
- 대량 스펙 corpus 운영에서 재변환과 vector DB re-index 대상을 줄이는 기준으로 사용합니다.

### `requirement_change_impact_report.json`

- `--input-dir`와 `--previous-corpus-manifest`를 함께 사용할 때 `corpus_diff_report.json`과 같이 생성됩니다.
- 이전/현재 `requirement_traceability_rag.jsonl`을 비교해 requirement 단위 `added`, `changed`, `removed`와 원문 `source_refs`를 기록합니다.
- 문장 요약이나 영향 추론을 하지 않고, AI Agent가 후속 impact analysis/test script 수정 범위를 찾을 수 있는 provenance만 제공합니다.

### 종료 코드와 리포트 해석

- `0`: 완전 성공
- `1`: 치명적 실패
- `2`: 부분 성공

`2`는 실패가 아니라, 보수적 fallback 또는 경고가 포함된 성공 실행일 수 있습니다.
예를 들어 복잡 표가 HTML fallback으로 직렬화되면 `report.json`의 `status`가
`partial_success`가 될 수 있습니다.

`--skip-existing`를 사용하면 기존 핵심 산출물이 있는 문서는 다시 처리하지 않고,
`batch_report.json`에서 `status == "skipped"` 와 `skipped == true`로 기록됩니다.

---

## 10. 운영 팁

### 표 모드 권장 사용처

| mode | 권장 상황 |
| --- | --- |
| `auto` | 기본 권장. 단순 표는 GFM, 복잡 표는 HTML fallback |
| `html` | 표 구조 보존이 최우선일 때 |
| `markdown` | 다운스트림이 GFM 중심이고 약간의 품질 손실을 감수할 때 |

### RAG / AI Code Assistant 운영 가이드

LLM RAG 등록이나 AI Code Assistant 컨텍스트 최적화 목적이라면 기본 권장 모드는 `auto`입니다.

- `auto`
  - 단순 표는 Markdown으로 유지하고, 복잡 표는 HTML fallback으로 구조를 보존합니다.
  - 토큰 효율과 구조 보존의 균형이 가장 좋습니다.
- `markdown`
  - 토큰 효율 최우선 모드입니다.
  - 복잡 표는 구조 손실이 발생할 수 있습니다.
- `html`
  - 표 구조 보존 최우선 모드입니다.
  - 복잡 표가 많은 스펙 문서에 적합합니다.

복잡 표가 많은 문서를 RAG에 등록할 때는 정본 Markdown을 억지로 GFM으로 바꾸기보다 아래 조합을 권장합니다.

```bash
python3 -m pdf2md input.pdf -o output/ --table-mode auto --rag-table-output both
```

- `document.md`: 사람이 검토할 정본입니다. 복잡 표는 HTML fallback으로 보존합니다.
- `text_blocks_rag.jsonl`: 본문 heading/paragraph/list/code/footnote/caption 블록을 page/bbox/heading_path와 함께 기록하는 기본 RAG sidecar입니다.
- `semantic_units_rag.jsonl`: section/requirement/definition/parameter/procedure_step/note/warning/reference를 원문과 provenance 중심으로 기록합니다.
- `requirements_rag.jsonl`: `semantic_units_rag.jsonl` 중 명확한 normative keyword가 있는 requirement만 별도 제공하는 filtered view입니다.
- `cross_refs_rag.jsonl`: Section/Clause/Table/Figure/Appendix와 requirement/log page/feature/opcode/register 참조의 resolved/unresolved 상태를 기록하며, technical ref는 normalized key, candidate count, unresolved reason을 함께 남깁니다.
- `requirement_traceability_rag.jsonl`: Requirement ID, condition, dependency, exception, testability hint를 원문 기반으로 기록합니다.
- `technical_tables_rag.jsonl`: register, bitfield, command/opcode, log page, feature identifier, enum/value table row를 typed sidecar로 기록합니다.
- `retrieval_chunks_rag.jsonl`: vector DB ingest 후보 chunk를 text/semantic/requirement/trace/table/technical/domain provenance와 함께 기록하며, 각 chunk에 `schema_version`과 원본 PDF `source_sha256`를 포함합니다. 긴 chunk는 token budget 기준으로 deterministic split되고 `parent_chunk_id`, `chunk_part_index`, `chunk_part_count`가 보존됩니다.
- `figures_rag.jsonl`: 이미지/도표 bbox, caption, OCR 후보, nearby heading, figure kind를 별도 기록합니다.
- `rag_tables.md`: 검색 chunk에 넣기 쉬운 행 단위 Markdown입니다.
- `tables_rag.jsonl`: `table_id`, `table_row_id`, `page`, `table_index`, `headers`, `cells`, `row_text`, `bbox`, `quality_score`, `fallback_reasons`를 가진 행 단위 JSONL입니다.
- `domain_units_rag.jsonl`: `--domain-adapter nvme|pcie|ocp|tcg|customer-requirements` 사용 시 domain unit을 기록합니다.
- 텍스트 블록 sidecar는 본문을 요약하거나 재서술하지 않고, 추출된 원문 블록과 provenance만 기록합니다.
- semantic sidecar도 요약/재서술/설명 생성을 하지 않고, 명확한 스펙 신호만 보수적으로 분류합니다.
- sidecar는 셀 텍스트를 요약하거나 해석하지 않고, 추출된 셀을 행 단위로 재배열만 합니다.
- 캡션은 확실한 인접 table caption만 연결하고, 불확실하면 비워 둡니다.
- multi-row header가 명확하면 `Parent / Child` 형태로 flatten하고, 첫 번째 열이 row label이면 `stub_cells`에 별도 기록합니다.
- header 판단이 불확실하면 원문 header를 유지하고 `LOW_HEADER_CONFIDENCE`를 fallback reason에 남깁니다.
- adjacent page의 header가 명확히 같은 표는 `continuation_group` metadata로만 연결하고, 확신이 낮으면 연결하지 않습니다.

RAG 검색 품질을 로컬 deterministic 방식으로 점검하려면 `retrieval_chunks_rag.jsonl`이 있는 출력 폴더와 질의 fixture를 지정합니다. Indexer별 field mapping과 운영 checklist는 [docs/RAG_INDEXER_INTEGRATION_RECIPES.md](docs/RAG_INDEXER_INTEGRATION_RECIPES.md)에 정리되어 있습니다.

```bash
./.venv311/bin/python scripts/run_rag_eval.py --output-dir output --eval-set rag_eval_queries.json --top-k 5
./.venv311/bin/python scripts/run_rag_eval.py --output-dir output --eval-set rag_eval_queries.json --top-k 5 --min-expected-source-coverage 0.9 --min-requirement-coverage 0.9 --min-table-field-coverage 0.85 --min-cross-ref-resolved-coverage 0.8 --max-chunk-token-p95 512 --max-conversion-duration-ms 10000 --fail-on-threshold
./.venv311/bin/python scripts/run_rag_eval.py --output-dir output --eval-set rag_eval_queries.json --calibration-profile docs/rag_calibration_profile.example.json --fail-on-threshold
```

Eval fixture에는 `expected_source_ids`와 `expected_source_types` 외에 `expected_requirement_source_ids`, `expected_table_field_source_ids`를 넣을 수 있으며 report에는 hit@k, MRR, citation coverage, expected source coverage, requirement coverage, table-field coverage, cross-reference resolved coverage, chunk token 분포, conversion duration이 기록됩니다.

`rag_eval_report.json`에는 hit@k, MRR, expected source coverage, query별 retrieved chunk/source id, missing expected source id, threshold 통과/실패 정보가 기록됩니다.

SSD 검증 에이전트 연동 운영에서는 `document.md` 단독 업로드보다 `retrieval_chunks_rag.jsonl` 중심의 sidecar-aware ingest를 권장합니다. Secure RAG adapter는 `chunk_id`, `text`, `page_range[0]`, `section_path`, `source_refs`, `schema_version`, `source_sha256`를 SSD 에이전트의 `RagChunk/RagCitation` metadata로 보존해야 합니다.

```bash
python3 -m pdf2md nvme.pdf -o output/nvme --domain-adapter nvme --rag-table-output jsonl --remove-header-footer --confidential-safe-mode
python3 scripts/validate_ssd_rag_contract.py --output-dir output/nvme --ssd-agent-domain HIL --ssd-agent-spec-type NVMe --domain-adapter nvme
python3 scripts/validate_ssd_rag_contract.py --output-dir output/tcg --ssd-agent-domain HIL --ssd-agent-spec-type TCG --domain-adapter tcg
python3 scripts/run_ssd_corpus_profile.py --profile local_ssd_corpus_profile.json --fail-on-error
python3 scripts/run_ssd_corpus_profile.py --profile local_ssd_corpus_profile.json --fail-on-error --evidence-pack
```

Profile mapping은 `nvme -> HIL/NVMe`, `pcie -> HIL/PCIe`, `ocp -> HIL/OCP`, `tcg -> HIL/TCG`를 기준으로 합니다. TCG는 `CustomerRequirement` fallback 없이 first-class `spec_type=TCG`로 검증합니다. `tables_rag.jsonl`은 운영 profile에서 `--rag-table-output jsonl|both`로 생성하고, `domain_units_rag.jsonl`은 profile별 `--domain-adapter`를 필수로 지정해 생성합니다. Profile 문서에 `eval_set`, `rag_thresholds`, `top_k`를 넣으면 document별 `rag_eval_report.json`과 domain/spec별 aggregate metric도 `ssd_corpus_profile_report.json`에 기록됩니다. `--evidence-pack`은 비공개 corpus 실패 패턴을 raw path, command, filename, query text 없이 `local_corpus_evidence_pack.json` signature 집계로 따로 기록합니다.

### 구조 마커 복구 운영 포인트

- tiny 좌측 여백 섹션 인덱스는 가능한 경우 텍스트로 복구되고, 불확실하면 이미지 재삽입 없이 suppress 됩니다.
- 복구 결과는 `manifest.json > excluded_images[]` 와 `report.json > summary` 에 남습니다.
- 운영 점검 순서 권장:
  - `document.md` 에서 구조 번호가 실제 heading처럼 읽히는지 확인
  - `manifest.json` 에서 `recovery_strategy` 와 `ocr_candidates` 확인
  - `report.json` 에서 `structure_marker_suppressed_count` 가 비정상적으로 높지 않은지 확인

### 이미지 모드별 파일 생성 규칙

- `referenced`: `assets/images/`에 실제 이미지 파일을 저장하고 Markdown에서 상대경로로 참조
- `embedded`: base64 data URI를 사용하며 이미지 파일을 별도로 저장하지 않음
- `placeholder`: Markdown comment만 남기고 이미지 파일을 저장하지 않음

### OCR 사용 시 주의

- OCR을 사용하려면 시스템에 Tesseract가 설치되어 있어야 합니다.
- `OCR_RUNTIME_UNAVAILABLE` warning이 나오면 `tesseract --version`과 PATH를 먼저 확인하세요.
- 한국어 OCR은 시스템 Tesseract에 해당 언어 데이터가 있어야 하며, 필요 시 `--ocr-lang kor+eng`처럼 지정합니다.

---

## 11. 테스트 실행 예시

```bash
python -m pytest
```

특정 테스트만 실행:

```bash
python -m pytest tests/test_cli.py -q
python -m pytest tests/test_markdown_serializer.py -q
python -m pytest tests/test_tables.py -q
```

가상환경이 `.venv311`인 경우 예시:

```bash
./.venv311/bin/python -m pytest
```

### Golden corpus / 성능 점검

저작권 있는 실제 PDF는 repo에 커밋하지 않고, 로컬 `pdf/` 디렉터리에서만 평가합니다.
synthetic fixture는 `tests/golden/corpus/`의 golden과 비교해 회귀를 막습니다.

```bash
./.venv311/bin/python scripts/run_corpus_eval.py --input-dir pdf --output-dir pdf/eval_output
./.venv311/bin/python scripts/run_corpus_eval.py --input-dir pdf --output-dir pdf/eval_output --baseline-report pdf/baseline/corpus_eval_report.json --max-partial-rate 0.1 --max-low-quality-table-rate 0.05 --min-pages-per-second 1.0 --fail-on-regression
./.venv311/bin/python scripts/benchmark_conversion.py --output-dir /tmp/pdf2md-benchmark --page-counts 10,50,100
./.venv311/bin/python scripts/benchmark_conversion.py --output-dir /tmp/pdf2md-benchmark --page-counts 10,50,100 --baseline-report /tmp/pdf2md-baseline/benchmark_report.json --max-duration-regression 0.2 --max-memory-regression 0.2 --min-pages-per-second 1.0 --fail-on-regression
./.venv311/bin/python scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-gates --gates ocr,corpus,benchmark,schema,packaging --corpus-input-dir pdf --corpus-baseline-report pdf/baseline/corpus_eval_report.json --benchmark-baseline-report /tmp/pdf2md-baseline/benchmark_report.json
./.venv311/bin/python scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-rag --gates rag --rag-output-dir output --rag-eval-set rag_eval_queries.json --rag-min-expected-source-coverage 0.9 --rag-min-requirement-coverage 0.9 --rag-min-table-field-coverage 0.85 --rag-min-cross-ref-resolved-coverage 0.8
```

- `corpus_eval_report.json`: success/partial 집계, fallback reason, suppressed line, low quality table, pages/sec, pdf open count, text line extract count, regression summary
- `benchmark_report.json`: page count별 duration, stage duration, pages/sec, pdf open count, text line extract count, peak memory, regression summary
- `rag_eval_report.json`: hit@k, MRR, expected source coverage, requirement/table-field/cross-ref coverage, chunk token 분포, threshold summary
- `release_gate_report.json`: OCR preflight, corpus quality gate, benchmark performance gate, optional RAG calibration gate, schema check, packaging smoke command/status summary
- benchmark는 수동/릴리스 전 검증용이며 기본 CI 테스트에는 포함하지 않습니다.
- 패키징 smoke는 릴리스 전에 `python -m build`, wheel 설치 후 `python -m pdf2md --help`, `pdf2md --help` 순서로 확인합니다.
- GitHub Actions CI는 PR/push마다 `python -m pytest`와 `python -m pdf2md --help`를 실행합니다.
- 향후 작업 backlog는 [docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md](docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md)에 새 작업만 남기고, 완료된 항목은 제거합니다.
- active 개발 명세는 [docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md](docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md)에 작성하고, 완료된 명세는 [docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md](docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md)에 보관합니다.

lint / format 도입 시 예시:

```bash
ruff check .
ruff format .
```

---

## 12. 향후 로드맵

### 현재 안정화 이후 우선순위

- 다음 작업은 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 등록하고, 완료되면 해당 문서에서 제거합니다.
- 현재 active quality backlog는 없습니다. 새 개선 과제가 발견되면 Next Plan에 신규 Q 항목을 먼저 추가합니다.

### 이후 후보

- 이미지 설명 생성 옵션
- backend adapter 확장
- appendix/comment/json 기반 추가 출력 모드

---

## 13. 구현 원칙 요약

이 프로젝트에서 가장 중요한 판단 기준은 아래와 같습니다.

1. **원문을 바꾸지 말 것**
2. **애매하면 더 보수적인 형식을 선택할 것**
3. **잘못된 예쁘기보다 덜 예쁜 정확함을 선택할 것**
4. **실패를 숨기지 말고 기록할 것**
5. **반복 실행 시 같은 결과가 나오게 만들 것**
