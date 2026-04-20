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
- `manifest.json`, `report.json`, `batch_report.json`으로 재처리 가능한 메타데이터 제공

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

### 테이블

- 단순 표는 GFM pipe table로 출력합니다.
- 복잡 표는 HTML fallback을 우선합니다.
- `--table-mode auto|html|markdown`을 지원합니다.
- `html-only`, `gfm-only`는 legacy compatibility mode로 유지됩니다.

### 이미지

- 기본 모드는 `referenced`입니다.
- `assets/images/` 아래에 이미지 파일을 저장하고 Markdown 본문에서는 상대경로로 연결합니다.
- `embedded`, `placeholder`도 선택적으로 지원합니다.
- 인접 캡션이 확실한 경우 `caption_text`, `caption_source`를 metadata에 기록합니다.

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
    report.py
  utils/
    io.py
    logging.py
    page_range.py
    pdf.py
    structure.py
tests/
  ...
scripts/
  validate_python_matrix.sh
  setup_windows_env.ps1
  setup_windows_env.bat
  run_batch_folder_windows.ps1
  run_batch_folder_windows.bat
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

### 페이지 마커 제어

```bash
python3 -m pdf2md input.pdf -o output/ --keep-page-markers
python3 -m pdf2md input.pdf -o output/ --no-page-markers
```

### 실행 로그 보기

```bash
pdf2md input.pdf -o output/ --verbose
pdf2md input.pdf -o output/ --debug
```

### 기존 배치 산출물이 있으면 건너뛰기

```bash
python3 -m pdf2md --input-dir ./pdfs --skip-existing
```

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
  assets/
    images/
      page-0001-figure-001.png
      page-0002-figure-002.png
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
- 이미지별 `alt_text`
- 인접 캡션이 확실할 때만 `caption_text`, `caption_source`
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
- `summary.page_status_counts`
- `summary.table_mode_requested`
- `summary.table_quality`
- `summary.table_fallback_count`
- `summary.table_fallbacks`
- `summary.table_markdown_forced_count`
- `summary.table_html_forced_count`
- `summary.structure_marker_recovered_count`
- `summary.structure_marker_recovered_exact_count`
- `summary.structure_marker_recovered_context_count`
- `summary.structure_marker_suppressed_count`

### `batch_report.json`

- 배치 모드에서만 생성되는 집계 파일
- 처리 대상 PDF 목록
- 문서별 상태: `success`, `partial_success`, `failed`, `skipped`
- 문서별 출력 경로와 파일 경로
- 문서별 종료 코드
- 문서별 `warning_count`, `table_count`, `image_count`, `used_ocr`, `skipped`
- 전체 성공/부분성공/실패/건너뛰기 집계

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

lint / format 도입 시 예시:

```bash
ruff check .
ruff format .
```

---

## 12. 향후 로드맵

### 현재 안정화 이후 우선순위

- 복잡 표 HTML fallback 고도화
- 멀티컬럼 reading order 개선
- header/footer 제거 옵션
- image dedupe
- debug artifact 개선

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
