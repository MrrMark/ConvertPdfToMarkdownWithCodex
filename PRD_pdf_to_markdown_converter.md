# PRD - PDF to Markdown 변환기

## 1. 문서 개요

- 문서명: PDF to Markdown Converter 개발 요구사항
- 목적: PDF 문서를 열어 Markdown(`.md`)으로 변환하는 프로그램을 개발한다.
- 사용 대상: GPT Codex를 활용해 실제 구현을 진행할 개발자 / AI 코딩 에이전트
- 문서 성격: 구현 지시가 가능한 실무형 요구사항 문서
- 우선순위: **텍스트 보존 정확도 > 테이블 구조 보존 정확도 > 이미지 위치/연결 정확도 > 부가 메타데이터 풍부성**

---

## 2. 배경

Anthropic PDF Skill 기반 워크플로를 참고하여, PDF를 안정적으로 읽고 텍스트 / 테이블 / 이미지 / 스캔 문서를 Markdown으로 변환하는 로컬 프로그램을 개발한다.

이 프로그램의 핵심 요구는 다음과 같다.

1. **텍스트는 요약/의역 없이 원문 그대로 출력**해야 한다.
2. **테이블은 가능한 한 테이블 구조 그대로 유지**해야 한다.
3. **이미지는 Markdown 문서 안에서 의미를 잃지 않도록 위치와 참조가 보존**되어야 한다.
4. 디지털 PDF뿐 아니라 **스캔 PDF(OCR 필요)** 도 처리할 수 있어야 한다.
5. 결과물은 사람이 읽기에도 무난해야 하지만, 1차 목적은 **정확하고 재처리 가능한 Markdown 산출물**이다.

---

## 3. 제품 목표

### 3.1 목표

- PDF 1개를 입력받아 Markdown 1개와 관련 asset 디렉터리를 생성한다.
- 본문 텍스트의 순서와 구조(제목, 문단, 목록, 인용문, 코드 유사 블록 등)를 최대한 유지한다.
- 표는 단순 표는 GFM 표로, 복잡 표는 HTML table fallback으로 안정적으로 직렬화한다.
- 이미지는 문서 내 상대경로 링크 방식으로 추출/참조한다.
- OCR이 필요한 페이지는 자동 감지하거나 옵션으로 강제 OCR 처리한다.
- CLI 및 Python 라이브러리 형태를 모두 제공한다.
- 테스트 가능한 결정적(deterministic) 출력 규칙을 가진다.

### 3.2 비목표

- PDF를 완벽하게 WYSIWYG 재현하는 렌더러를 만드는 것은 본 범위가 아니다.
- DTP 수준의 레이아웃 복원은 목표가 아니다.
- VLM 기반 이미지 설명 생성은 기본 기능이 아니라 선택 기능이다.
- 벡터 다이어그램의 의미 해석, 차트 데이터 재구성, 수식 의미 해석은 v1 필수 범위가 아니다.

---

## 4. 설계 원칙

### 4.1 원문 보존 원칙

- 텍스트를 재서술, 요약, 교정하지 않는다.
- OCR 결과라도 후처리는 최소화하고, 정규화가 필요한 경우도 **의미 변경 없는 범위**로 제한한다.
- 공백 정리는 하되, 문단/표/목록 경계를 깨뜨리면 안 된다.

### 4.2 구조 보존 원칙

- 제목은 Markdown heading으로 변환한다.
- 목록은 ordered / unordered list로 유지한다.
- 표는 표로 유지한다.
- 이미지는 문서 내 등장 위치 근처에 배치한다.

### 4.3 안전한 fallback 원칙

- GFM 표로 안전하게 표현 가능한 경우만 pipe table을 사용한다.
- 병합 셀(rowspan / colspan), 다중 헤더, 셀 내부 복합 블록이 있는 경우 HTML table로 fallback 한다.
- 이미지 inline embedding으로 결과가 비대해질 수 있으면 referenced image를 기본값으로 사용한다.

### 4.4 재현 가능성 원칙

- 같은 입력 + 같은 옵션이면 항상 동일한 산출물을 생성해야 한다.
- 파일명 규칙, 페이지 마커, 이미지 번호, 표 번호 규칙을 고정한다.

---

## 5. 리서치 요약 및 구현 시사점

### 5.1 Anthropic PDF Skill 기준 반영

구현의 기본 골격은 Anthropic PDF Skill에서 제시하는 PDF 처리 관점을 따른다.

- 기본 PDF 조작: `pypdf`
- 텍스트 / 테이블 추출: `pdfplumber`
- 텍스트 레이아웃 보존 추출 보조: `pdftotext -layout`
- 이미지 추출: `pdfimages` 또는 동등 기능
- 스캔 PDF OCR: `pytesseract` 기반

즉, **v1 기본 스택은 Python 중심 + 필요 시 poppler CLI 보조 방식**으로 설계한다.

### 5.2 오픈소스 도구들의 일반적 패턴

공개된 PDF→Markdown 계열 도구들을 조사했을 때, 공통적으로 다음 패턴이 반복된다.

1. 텍스트/표/이미지를 분리 추출한다.
2. 이미지는 별도 파일로 저장하고 Markdown에서 상대경로로 참조한다.
3. 일부 도구는 embedded/base64 이미지도 지원하지만, 이는 파일 크기를 크게 키운다.
4. 고정밀 인간 가독성보다 LLM/후처리 친화적인 구조화를 우선하는 도구도 많다.
5. 선택적으로 AI 이미지 설명을 붙이는 도구도 있으나, 기본 출력과는 분리하는 편이 안전하다.

### 5.3 본 프로젝트에 대한 결론

본 프로젝트의 기본 전략은 다음으로 확정한다.

- **기본 이미지 처리 모드: referenced**
- **보조 모드: placeholder / embedded**
- **기본 출력은 비환각(non-hallucinatory)**
- **AI 기반 이미지 설명은 옵션 기능**
- **표는 GFM 우선, 복잡 표는 HTML fallback**

---

## 6. 권장 출력 규격

### 6.1 산출물 디렉터리 구조

```text
output/
  document.md
  assets/
    images/
      page-0001-figure-001.png
      page-0002-figure-002.png
    tables/
      page-0003-table-001.png
  manifest.json
  report.json
```

### 6.2 기본 Markdown 문서 규칙

- 출력 파일명 기본값: 입력 PDF basename + `.md`
- 인코딩: UTF-8
- 줄바꿈: LF
- 페이지 구분자는 옵션으로 켜고 끌 수 있어야 한다.
- 기본 페이지 마커 형식:

```md
<!-- page: 1 -->
```

### 6.3 제목/문단 규칙

- 폰트 크기, 위치, 스타일을 종합해 heading level 추정
- 확신도가 낮을 경우 일반 문단으로 처리
- 문단은 문장 단위가 아니라 **시각적으로 연속된 텍스트 블록 단위**로 묶는다.

### 6.4 표 출력 규칙

#### 6.4.1 GFM 표 사용 조건

다음 조건을 모두 만족할 때만 GFM pipe table 사용:

- 열/행 구조가 직사각형으로 복원 가능
- 병합 셀이 없음
- 셀 내부에 복합 블록(목록, 코드 블록, 복수 문단)이 없음
- 셀 텍스트를 한 줄 또는 안전한 줄바꿈으로 표현 가능

예시:

```md
| 항목 | 값 | 비고 |
| --- | --- | --- |
| 이름 | 홍길동 | 예시 |
| 점수 | 95 | 통과 |
```

#### 6.4.2 HTML table fallback 조건

다음 중 하나라도 해당하면 HTML table 사용:

- rowspan / colspan 존재
- 다중 헤더 행 존재
- 셀 내부 리스트/복수 문단 존재
- 표가 지나치게 넓어 GFM 직렬화 시 의미 손실 발생
- 셀 경계 복원이 불완전하여 GFM 표가 오해를 유발할 가능성이 높음

예시:

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

#### 6.4.3 표 위치 보존

- 표는 원문에서 등장한 순서대로 출력한다.
- 필요 시 아래 주석을 붙여 추적 가능하게 한다.

```md
<!-- table: page=3 index=1 mode=gfm -->
```

또는

```md
<!-- table: page=5 index=2 mode=html -->
```

### 6.5 이미지 출력 규칙

#### 6.5.1 기본 모드: referenced

기본값은 **이미지를 파일로 추출하고 Markdown에서 상대경로로 참조**하는 방식이다.

예시:

```md
![Figure 1](./assets/images/page-0002-figure-001.png)

*Figure 1. 매출 추이 그래프*
```

#### 6.5.2 보조 모드

- `placeholder`: 이미지 위치만 표시
- `embedded`: base64 data URI로 인라인 포함
- `referenced`: 외부 PNG/JPG 파일로 저장 후 링크

#### 6.5.3 캡션 처리 규칙

Markdown 표준 이미지 문법에는 캡션 전용 문법이 없으므로, 다음 중 하나를 사용한다.

1. **기본 방식**: 이미지 아래 한 줄 이탤릭 캡션
2. **선택 방식**: HTML `<figure>` / `<figcaption>` 사용

기본 권장 형식:

```md
![Figure 2](./assets/images/page-0010-figure-003.png)

*Figure 2. 실험 구성도*
```

#### 6.5.4 alt text 규칙

alt text는 다음 우선순위로 생성한다.

1. 원문 figure caption
2. 인접한 제목/라벨 (`Figure 1`, `그림 2`, `도표 3` 등)
3. 없으면 기계적 기본값 (`Image page-0010-figure-003`)

#### 6.5.5 이미지 설명 생성 정책

- 기본값: **비활성화**
- 옵션명 예시: `--describe-images`
- 활성화 시에도 Markdown 본문에 바로 주입하지 말고 아래 중 하나를 선택 가능하게 한다.
  - 주석 블록
  - 별도 sidecar JSON
  - appendix 섹션

기본 동작은 절대 환각된 서술을 본문에 넣지 않는다.

---

## 7. 기능 요구사항

## 7.1 입력

프로그램은 다음 입력을 지원해야 한다.

- 단일 PDF 파일 경로
- 비밀번호가 걸린 PDF (옵션으로 비밀번호 제공)
- 페이지 범위 지정
- OCR 강제 여부
- 이미지 모드 선택
- 출력 디렉터리 지정

예시 CLI:

```bash
pdf2md input.pdf -o ./output
pdf2md input.pdf -o ./output --pages 1-5
pdf2md input.pdf -o ./output --image-mode referenced
pdf2md input.pdf -o ./output --force-ocr
```

## 7.2 출력

프로그램은 최소 다음 파일을 생성해야 한다.

- `document.md`
- `manifest.json`
- `report.json`
- 필요 시 `assets/` 디렉터리

### 7.2.1 manifest.json 요구사항

`manifest.json`에는 최소 아래 정보가 포함되어야 한다.

- 입력 파일명
- 총 페이지 수
- 처리 옵션
- 이미지 목록 (page, index, path, bbox, width, height, sha256)
- 표 목록 (page, index, mode=gfm|html, bbox)
- OCR 적용 페이지 목록
- 경고 / fallback 목록

### 7.2.2 report.json 요구사항

`report.json`에는 실행 보고 정보가 포함되어야 한다.

- 시작/종료 시각
- 총 처리 시간
- 추출 엔진별 사용 여부
- 실패한 페이지/요소
- 경고 메시지
- summary statistics

## 7.3 텍스트 추출

프로그램은 다음을 만족해야 한다.

- PDF의 읽기 순서를 최대한 복원한다.
- 멀티컬럼 문서를 가능한 범위에서 올바른 순서로 합친다.
- 하이픈 줄바꿈 처리 옵션 제공
- 머리말/꼬리말 제거 옵션 제공
- 각주/주석 보존 옵션 제공
- 코드 블록 유사 영역(고정폭/정렬 패턴)은 fenced code block 후보로 처리 가능해야 한다.
- 링크가 추출 가능하면 Markdown 링크로 변환한다.

### 7.3.1 텍스트 정규화 규칙

- Unicode normalization은 NFC 기준
- 연속 공백 축약은 문단 내부에서만 제한적으로 수행
- 의미 없는 라인브레이크만 제거
- 페이지 넘김으로 인한 단어 쪼개짐은 옵션으로 복구

## 7.4 테이블 추출

프로그램은 다음을 만족해야 한다.

- 페이지 내 테이블 후보를 감지한다.
- 표 영역은 본문보다 우선적으로 구조 추출을 시도한다.
- 표 셀 텍스트는 셀 내부 reading order를 따른다.
- 표 제목(caption)과 표 본문이 분리되어 있으면 재결합을 시도한다.
- 표가 여러 페이지에 걸쳐 이어질 경우 `continued` metadata를 남긴다.
- 불완전 복원 표는 HTML fallback 또는 이미지 fallback 중 선택 가능해야 한다.

## 7.5 이미지 추출

프로그램은 다음을 만족해야 한다.

- embedded raster image를 우선 추출한다.
- embedded image가 없고, figure 영역만 존재하는 경우 페이지 crop 방식 fallback을 지원한다.
- 동일 이미지가 반복 삽입된 경우 dedup 옵션을 지원한다.
- 이미지 포맷은 기본 PNG, 원본 보존 가능하면 원본 확장자 유지 옵션 제공
- 문서 내 위치 근처에 이미지 참조를 배치한다.

## 7.6 OCR

프로그램은 스캔 PDF를 지원해야 한다.

### 7.6.1 OCR 적용 조건

- 텍스트 레이어가 없거나 품질이 현저히 나쁠 때 자동 OCR
- 사용자 옵션으로 전체 페이지 강제 OCR 가능
- 페이지 단위 OCR / 문서 전체 OCR 둘 다 가능

### 7.6.2 OCR 출력 규칙

- OCR 텍스트도 동일한 Markdown 직렬화 파이프라인을 거친다.
- OCR confidence가 낮은 블록은 report에 경고를 남긴다.
- OCR 결과로 생성된 heading / table / caption은 confidence 기반 보수적으로 처리한다.

## 7.7 오류 처리

다음 상황에서 프로그램은 비정상 종료보다 부분 성공(partial success)을 우선한다.

- 특정 페이지만 추출 실패
- 특정 표만 구조 복원 실패
- 특정 이미지 추출 실패
- OCR 엔진 일부 실패

오류 시 정책:

- 실패 지점을 report.json에 기록
- 가능한 범위의 Markdown은 계속 생성
- 실패한 위치에 주석 또는 placeholder 삽입 가능

예시:

```md
<!-- warning: image extraction failed page=7 index=2 -->
```

---

## 8. 비기능 요구사항

### 8.1 성능

- 100페이지 내 일반 문서는 실용 시간 내 처리되어야 한다.
- 페이지 단위 병렬 처리 옵션을 제공한다.
- 단, 출력 순서는 항상 원문 순서를 보장해야 한다.

### 8.2 정확성

- 단순 디지털 PDF에서 본문 누락률을 최소화해야 한다.
- 단순 표는 높은 확률로 GFM 표로 출력되어야 한다.
- 복잡 표는 잘못된 GFM 표보다 HTML fallback이 우선이다.

### 8.3 이식성

- Python 3.11+ 기준
- macOS / Linux 우선 지원
- Windows는 선택 지원

### 8.4 관측 가능성

- verbose logging 지원
- page 단위 처리 로그
- debug mode에서 intermediate artifacts 저장 가능

### 8.5 결정성

- 동일 옵션/동일 버전/동일 입력이면 동일 파일명과 동일 직렬화 결과 보장

---

## 9. 권장 기술 스택

### 9.1 필수

- Python 3.11+
- `pypdf` : 문서 메타데이터, 페이지 접근, 기본 PDF 구조 처리
- `pdfplumber` : 텍스트 / 표 추출
- `pytesseract` : OCR
- `Pillow` : 이미지 저장/후처리
- `typer` 또는 `argparse` : CLI
- `pydantic` : 설정 / manifest / report schema

### 9.2 권장 외부 도구

- `pdftotext` : 레이아웃 기반 텍스트 추출 비교용
- `pdfimages` : embedded 이미지 추출 보조
- `tesseract` CLI : OCR 엔진

### 9.3 선택적 확장

- `PyMuPDF` / `pymupdf4llm` : 대체 추출 백엔드 실험
- `docling` : 고급 이미지 모드 / 문서 구조 실험용 adapter
- VLM provider (OpenAI / Anthropic / Gemini 등): 이미지 설명 선택 기능

---

## 10. 권장 아키텍처

```text
pdf2md/
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

### 10.1 처리 파이프라인

1. 입력 PDF 로드
2. 메타데이터 읽기
3. 페이지별 텍스트 레이어 유무 판정
4. OCR 필요 여부 판정
5. 본문 / 표 / 이미지 후보 영역 추출
6. 블록별 reading order 정렬
7. Markdown 블록으로 직렬화
8. asset 저장
9. manifest / report 작성

---

## 11. CLI 요구사항

### 11.1 기본 명령

```bash
pdf2md INPUT_PDF [OPTIONS]
```

### 11.2 주요 옵션

```text
-o, --output-dir PATH
--pages TEXT
--password TEXT
--image-mode [referenced|embedded|placeholder]
--table-mode [auto|gfm-only|html-only]
--force-ocr
--ocr-lang TEXT
--remove-header-footer
--keep-page-markers / --no-page-markers
--describe-images
--describe-images-output [comment|json|appendix]
--dedupe-images
--debug
--verbose
```

### 11.3 종료 코드

- `0`: 성공
- `1`: 치명적 실패
- `2`: 부분 성공 (일부 페이지/요소 실패)

---

## 12. 직렬화 세부 규칙

### 12.1 본문 블록 우선순위

한 페이지에서 블록 직렬화 순서는 다음을 따른다.

1. heading
2. paragraph
3. list
4. table
5. image
6. footnote / appendix-like block

단, 실제 출력은 page 좌표 기반 reading order를 우선하되, table/image는 독립 블록으로 승격한다.

### 12.2 이미지 주변 텍스트 결합 규칙

- `Figure N`, `그림 N`, `도 N`, `Chart N` 패턴이 있으면 image caption 후보로 우선 연결
- 이미지 직전/직후 1~2개 짧은 문단을 caption 후보로 탐색
- caption 확신도 낮으면 연결하지 말고 일반 문단 유지

### 12.3 표 주변 텍스트 결합 규칙

- `Table N`, `표 N` 패턴을 표 캡션 후보로 탐색
- 캡션은 표 위/아래 모두 허용
- 확신도 낮으면 표와 분리 유지

---

## 13. 테스트 요구사항

## 13.1 테스트 세트

최소 아래 fixture PDF를 포함한다.

- 일반 단일 컬럼 문서
- 멀티컬럼 문서
- 단순 표 포함 문서
- 병합 셀 포함 복잡 표 문서
- 이미지 다수 포함 문서
- 스캔 PDF
- 한글 문서
- 영문 문서
- 비밀번호 PDF

## 13.2 테스트 유형

- unit test
- integration test
- golden file regression test
- CLI smoke test

## 13.3 검증 항목

- Markdown 문법 유효성
- 이미지 파일 생성 여부
- 상대경로 링크 유효성
- 표 모드 선택 정확성 (GFM vs HTML)
- OCR 페이지 감지 정확성
- manifest / report schema 유효성

---

## 14. 수용 기준 (Acceptance Criteria)

다음 조건을 만족하면 v1 완료로 본다.

1. 단일 PDF를 CLI로 입력하면 `.md` 파일이 생성된다.
2. 텍스트가 요약되지 않고 원문 순서대로 대부분 유지된다.
3. 단순 표는 GFM 표로 출력된다.
4. 복잡 표는 HTML table fallback으로 안전하게 출력된다.
5. 이미지는 기본적으로 `assets/images/...`에 저장되고 Markdown에 상대경로로 연결된다.
6. OCR이 필요한 PDF에서 `--force-ocr` 또는 자동 감지로 텍스트 출력이 가능하다.
7. manifest.json / report.json 이 생성된다.
8. 일부 페이지 실패 시에도 부분 결과를 남기고 종료 코드로 상태를 구분한다.

---

## 15. v1 구현 우선순위

### P0

- CLI 동작
- 텍스트 추출
- 단순 표 GFM 출력
- 이미지 referenced 출력
- OCR 기본 지원
- manifest / report 생성

### P1

- 복잡 표 HTML fallback
- 멀티컬럼 개선
- header/footer 제거 옵션
- page marker 옵션
- image dedupe

### P2

- 이미지 설명 선택 기능
- PyMuPDF / Docling adapter
- appendix 출력 모드
- figure/table caption confidence model

---

## 16. Codex 구현 지시사항

- 먼저 **작동하는 최소 CLI 버전**을 만든다.
- 이후 extractor / serializer / detector 모듈로 분리한다.
- 각 단계마다 golden sample을 추가한다.
- `README.md` 와 `examples/` 를 함께 작성한다.
- 임시 추정 로직은 반드시 TODO와 제한사항을 명시한다.
- 표를 잘못 GFM으로 내보내는 것보다 HTML fallback을 우선 선택한다.
- 이미지는 기본적으로 referenced mode로 구현한다.
- embedded mode는 옵션으로만 제공한다.
- AI/VLM 설명 생성은 반드시 off-by-default 로 구현한다.

---

## 17. 최종 권고안

이 프로젝트의 기본 정책은 아래 한 줄로 요약한다.

> **텍스트는 그대로, 표는 안전하게, 이미지는 외부 파일 참조로, 애매하면 보수적으로 fallback 한다.**

즉, v1의 정답은 “가장 화려한 Markdown”이 아니라 “가장 신뢰할 수 있는 Markdown”이다.
