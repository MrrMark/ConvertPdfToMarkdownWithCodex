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

- PDF 1개를 입력받아 Markdown 1개와 관련 asset 디렉터리를 생성
- 디지털 PDF와 스캔 PDF(OCR 필요) 모두 처리
- 본문 순서, 제목, 문단, 목록, 표, 이미지 위치를 가능한 범위에서 안정적으로 복원
- 동일 입력 + 동일 옵션이면 동일 출력이 나오도록 deterministic 설계
- CLI와 Python API를 모두 제공
- `manifest.json`, `report.json`으로 재처리 가능한 메타데이터 제공

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

## 3. 기본 설계 방향

### 텍스트

- `pdfplumber` 중심으로 텍스트 추출
- 필요 시 `pdftotext -layout` 보조 활용
- 공백 정리는 최소화하되 의미 손실 금지
- OCR 결과도 과도하게 정리하지 않음

### 테이블

- 단순 표만 GFM pipe table로 출력
- 아래 경우는 HTML table fallback 우선
  - rowspan / colspan
  - 다중 헤더
  - 셀 내부 복수 문단
  - 리스트/코드/혼합 블록 존재
  - GFM으로 바꾸면 의미 손실 가능성이 큰 경우

### 이미지

- 기본 모드: `referenced`
- 이미지 파일은 `assets/images/` 아래 저장
- Markdown 본문에는 상대경로로 연결
- `embedded`, `placeholder`는 선택 모드로만 제공
- 이미지 설명 생성은 **기본 비활성화**

### OCR

- 스캔 PDF 또는 텍스트가 거의 없는 페이지에서 OCR 적용
- `--force-ocr` 옵션 제공
- OCR confidence가 낮으면 `report.json`에 warning 기록

### 실패 처리

- partial success 우선
- 특정 페이지/표/이미지 실패로 전체 문서를 중단하지 않음
- 실패와 경고는 `report.json`과 Markdown comment에 기록

---

## 4. 권장 기술 스택

### 핵심

- Python 3.11+
- `pypdf`
- `pdfplumber`
- `pydantic`
- `typer` 또는 `argparse`

### 보조 도구

- Poppler (`pdftotext`, `pdfimages`)
- Tesseract OCR (`pytesseract`)
- 필요 시 이미지 처리용 `Pillow`

### 테스트

- `pytest`
- golden output 비교 테스트
- CLI smoke test

---

## 5. 예상 프로젝트 구조

```text
pdf2md/
  __init__.py
  cli.py
  config.py
  models.py
  pipeline.py
  detectors/
    page_type.py
    heading.py
    table.py
    figure.py
  extractors/
    metadata.py
    text.py
    tables.py
    images.py
    ocr.py
  serializers/
    markdown.py
    html_table.py
    manifest.py
    report.py
  utils/
    files.py
    hashing.py
    bbox.py
    logging.py
  tests/
    fixtures/
    golden/
```

---

## 6. 설치 가이드

### Python 환경 생성

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
```

### 패키지 설치 예시

```bash
pip install -e .[dev]
```

### 시스템 의존성 예시

macOS:

```bash
brew install poppler tesseract
```

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr
```

> 실제 패키지명은 배포판/OS 환경에 따라 달라질 수 있으므로, 구현 단계에서 설치 체크 로직과 문서화를 함께 정리하는 것을 권장합니다.

---

## 7. CLI 사용 예시

### 가장 기본 실행

```bash
pdf2md input.pdf -o output/
```

### 일부 페이지만 변환

```bash
pdf2md input.pdf -o output/ --pages 1-3,5,7-9
```

### 강제 OCR

```bash
pdf2md input.pdf -o output/ --force-ocr
```

### 이미지 placeholder 모드

```bash
pdf2md input.pdf -o output/ --image-mode placeholder
```

### 테이블을 HTML 우선으로 출력

```bash
pdf2md input.pdf -o output/ --table-mode html-only
```

### 페이지 마커 제거

```bash
pdf2md input.pdf -o output/ --no-page-markers
```

---

## 8. 출력 구조

기본 출력 예시는 아래와 같습니다.

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

### `document.md`

- 최종 Markdown 본문
- 페이지 마커 옵션 지원
- 표/이미지 위치 보존 주석 포함 가능

### `manifest.json`

- 입력 파일명
- 처리 옵션
- 생성된 asset 목록
- 페이지 수 및 산출물 메타데이터

### `report.json`

- 처리 시간
- warning / failure
- OCR 적용 여부
- 페이지별 처리 결과 요약

---

## 9. Markdown 출력 규칙

### 페이지 마커

```md
<!-- page: 1 -->
```

### 단순 표

```md
| 항목 | 값 | 비고 |
| --- | --- | --- |
| 이름 | 홍길동 | 예시 |
| 점수 | 95 | 통과 |
```

### 복잡 표 fallback

```html
<table>
  <thead>
    <tr>
      <th colspan="2">요약</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>항목</td>
      <td>값</td>
    </tr>
  </tbody>
</table>
```

### 이미지 참조

```md
![Figure 1](./assets/images/page-0002-figure-001.png)

*Figure 1. 원문 캡션 또는 인접 설명*
```

---

## 10. 개발 우선순위

### P0

- CLI skeleton
- config / model 정의
- PDF 로딩 및 페이지 범위 처리
- 텍스트 추출
- 기본 Markdown serializer
- `manifest.json` / `report.json`
- 이미지 referenced 추출
- 단순 표 GFM 출력
- OCR 기본 지원
- partial success 및 종료 코드

### P1

- 복잡 표 HTML fallback 고도화
- 멀티컬럼 reading order 개선
- header/footer 제거 옵션
- image dedupe
- debug artifact 개선

### P2

- 이미지 설명 생성 옵션
- backend adapter 확장
- appendix/comment/json 기반 추가 출력 모드

---

## 11. 개발 체크리스트

작업 시 아래 체크를 반드시 수행합니다.

- [ ] `pdf2md --help` 동작
- [ ] 최소 1개 fixture에서 end-to-end 변환 성공
- [ ] golden output diff 확인
- [ ] `manifest.json` / `report.json` 생성 확인
- [ ] 단순 표는 GFM으로 출력되는지 확인
- [ ] 복잡 표는 보수적으로 HTML fallback 되는지 확인
- [ ] 이미지 파일이 상대경로로 정상 연결되는지 확인
- [ ] 스캔 PDF에서 OCR 경로가 작동하는지 확인
- [ ] partial success 정책이 유지되는지 확인

---

## 12. 테스트 실행 예시

```bash
pytest
```

특정 테스트만 실행:

```bash
pytest tests/test_cli.py -q
pytest tests/test_markdown_golden.py -q
```

lint / format 도입 시 예시:

```bash
ruff check .
ruff format .
```

---

## 13. 구현 원칙 요약

이 프로젝트에서 가장 중요한 판단 기준은 아래와 같습니다.

1. **원문을 바꾸지 말 것**
2. **애매하면 더 보수적인 형식을 선택할 것**
3. **잘못된 예쁘기보다 덜 예쁜 정확함을 선택할 것**
4. **실패를 숨기지 말고 기록할 것**
5. **반복 실행 시 같은 결과가 나오게 만들 것**

---

## 14. Codex 사용 팁

Codex에 작업을 넘길 때는 아래 방식이 가장 안정적입니다.

- 먼저 `PRD_pdf_to_markdown_converter.md`, `tasks.md`, `AGENTS.md`, `README.md`를 모두 읽게 하기
- 한 번에 전체 기능을 만들게 하기보다 **P0 최소 구현**부터 시키기
- 각 단계마다 테스트 실행과 결과 요약을 요구하기
- 복잡 표/이미지 설명처럼 난도가 높은 기능은 P1/P2로 미루기
- 결과 설명 시 “무엇을 구현했는지 / 무엇이 미완료인지 / 다음 작업이 무엇인지”를 분리해서 보고하게 하기

---

## 15. 다음 권장 작업

Codex 첫 작업은 아래 범위가 적절합니다.

1. 프로젝트 scaffold 생성
2. CLI 기본 진입점 구현
3. config/model 정의
4. PDF 로딩 + 페이지 범위 파서 구현
5. 최소 텍스트 추출 + Markdown serializer 구현
6. manifest/report 생성
7. 테스트 2~4개 추가

이후 이미지, 표, OCR을 순차적으로 붙이는 방식이 가장 안정적입니다.
