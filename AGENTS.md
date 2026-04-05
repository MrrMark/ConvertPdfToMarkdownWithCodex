# AGENTS.md

## 1. 목적

이 저장소의 목적은 **PDF를 Markdown으로 변환하는 신뢰성 높은 CLI/라이브러리**를 구현하는 것이다.

이 프로젝트에서 Codex가 가장 먼저 만족해야 하는 목표는 다음 순서다.

1. 텍스트 원문 보존 정확도
2. 테이블 구조 보존 정확도
3. 이미지 위치/참조 보존 정확도
4. 재처리 가능한 메타데이터 생성
5. 사람이 읽을 수 있는 수준의 Markdown 품질

화려한 출력보다 **신뢰 가능한 출력** 이 우선이다.

---

## 2. 소스 오브 트루스

작업 우선순위는 아래 문서 순서를 따른다.

1. 사용자 직접 지시
2. `PRD_pdf_to_markdown_converter.md`
3. `tasks.md`
4. 이 `AGENTS.md`
5. 코드 내 TODO / 주석

서로 충돌하면 더 상위 문서를 따른다.

---

## 3. 제품 원칙

### 3.1 텍스트

- 텍스트는 **요약, 재서술, 교정 없이 원문 그대로** 추출한다.
- OCR 결과도 의미를 바꾸는 후처리를 하지 않는다.
- normalization 은 의미 변경이 없는 범위(NFC, 안전한 공백 정리)에서만 허용한다.

### 3.2 테이블

- 표는 반드시 표로 출력한다.
- 단순 표만 GFM pipe table 을 사용한다.
- 애매하거나 복잡하면 **무조건 HTML table fallback** 을 우선한다.
- 잘못된 GFM 표는 금지한다.

### 3.3 이미지

- 기본 이미지 모드는 `referenced` 다.
- 이미지는 별도 파일로 저장하고 Markdown 에 상대경로로 연결한다.
- 이미지 설명 생성은 기본 비활성화다.
- 본문에 환각된 설명을 삽입하면 안 된다.

### 3.4 OCR

- OCR은 필요할 때만 적용한다.
- 강제 OCR 옵션은 지원하되, 기본 동작은 보수적으로 한다.
- confidence 가 낮으면 정답인 척 하지 말고 report 에 warning 을 남긴다.

### 3.5 실패 처리

- partial success 를 우선한다.
- 특정 페이지/표/이미지 실패로 전체 문서를 포기하지 않는다.
- 실패는 `report.json` 과 Markdown warning comment 로 기록한다.

### 3.6 결정성

- 동일 입력 + 동일 옵션 + 동일 버전이면 동일 출력이 나와야 한다.
- 파일명 규칙, asset 경로 규칙, JSON key 구조를 안정적으로 유지한다.

---

## 4. 구현 우선순위

Codex는 다음 순서로 구현한다.

### Phase 1 - 최소 제품

- CLI skeleton
- config / models
- PDF load / page range / password
- text extraction
- markdown serializer
- manifest / report

### Phase 2 - P0 완성

- image extraction referenced mode
- simple table GFM
- OCR
- partial success / exit code
- fixture / golden tests

### Phase 3 - P1

- complex table HTML fallback 강화
- multi-column reading order 개선
- header/footer 제거
- image dedupe
- debug artifacts

### Phase 4 - P2

- image description option
- backend adapters (PyMuPDF / Docling)
- appendix/comment/json outputs

P0가 안정화되기 전에는 P2에 시간을 쓰지 않는다.

---

## 5. 권장 아키텍처

아래 구조를 기본 기준으로 삼는다.

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
```

아키텍처를 바꿔도 되지만, 아래 원칙은 유지한다.

- CLI와 순수 로직을 분리할 것
- extractor 와 serializer 를 분리할 것
- manifest/report schema 를 코드로 강제할 것
- 실험적 backend 는 adapter 로 분리할 것

---

## 6. 코드 작성 규칙

### 6.1 일반 원칙

- Python 3.11+ 기준으로 작성한다.
- 타입 힌트를 적극 사용한다.
- public 함수에는 docstring 을 붙인다.
- 복잡한 heuristic 에는 왜 그렇게 했는지 주석으로 남긴다.
- 매직 넘버를 하드코딩하지 말고 상수/설정으로 올린다.

### 6.2 함수 설계

- 한 함수가 너무 많은 역할을 하지 않게 분리한다.
- 페이지 단위 처리 함수는 가능한 순수하게 유지한다.
- 예외 처리와 핵심 추출 로직을 뒤섞지 않는다.

### 6.3 로깅

- `print` 남발 금지
- 표준 logging 사용
- `--verbose`, `--debug` 옵션과 연결
- page 단위 로그를 남기되 과도한 noise 는 피한다.

### 6.4 에러 처리

- 라이브러리 예외를 그대로 삼키지 말고 구조화된 warning/report 로 변환한다.
- 치명적 실패와 부분 실패를 구분한다.
- 실패한 페이지 번호, asset index, 원인을 최대한 남긴다.

---

## 7. Markdown 직렬화 규칙

### 7.1 headings

- 확신이 높을 때만 heading 으로 승격한다.
- 확신이 낮으면 paragraph 로 남긴다.

### 7.2 paragraphs

- 시각적으로 연속된 블록 단위로 유지한다.
- 의미 없는 개행만 정리한다.

### 7.3 lists

- 명확한 ordered/unordered list 만 list 로 변환한다.
- 애매하면 문단으로 남긴다.

### 7.4 tables

- GFM 사용 전 반드시 안전성 검사
- 복잡성 감지 시 HTML fallback
- 표 주석(`<!-- table: ... -->`) 유지

### 7.5 images

- Markdown 에서는 상대경로 링크 사용
- 기본 캡션 형식은 이미지 아래 이탤릭 한 줄
- alt text 우선순위
  1. 원문 캡션
  2. 인접 라벨
  3. 기계적 기본값

---

## 8. 출력 파일 규칙

기본 산출물 구조는 아래를 따른다.

```text
output/
  document.md
  assets/
    images/
      page-0001-figure-001.png
  manifest.json
  report.json
```

규칙:

- UTF-8, LF 사용
- asset 파일명은 deterministic 하게 생성
- JSON 은 안정적 key 구조 유지
- 디버그 파일은 일반 출력과 분리

---

## 9. 테스트 규칙

Codex는 구현 후 반드시 테스트를 실행한다.

### 최소 요구 테스트

- unit tests
- integration tests
- CLI smoke test
- golden regression test

### fixture 우선순위

1. 일반 단일 컬럼
2. 단순 표
3. 이미지 포함 문서
4. 스캔 PDF
5. 복잡 표
6. 멀티컬럼
7. 한글 문서
8. 비밀번호 PDF

### 테스트 작성 원칙

- 새 heuristic 추가 시 회귀 테스트를 함께 추가한다.
- 버그를 고치면 reproducer fixture 또는 regression test 를 먼저 만든다.
- snapshot/golden 은 의도적 변경일 때만 갱신한다.

---

## 10. 권장 개발 명령

저장소에 실제 명령이 정해지면 그 명령을 우선한다.
아직 정해지지 않았다면 아래를 기본값으로 사용한다.

```bash
python -m pytest
python -m pytest tests/test_cli.py
python -m pytest tests/test_golden.py
python -m pdf2md --help
```

패키지 관리자/러너가 도입되면 문서를 업데이트한다.

---

## 11. 구현 시 주의사항

### 금지

- 복잡 표를 억지로 GFM 으로 내보내기
- 이미지 설명을 본문에 기본 삽입하기
- 실패 페이지 때문에 전체 산출물 삭제하기
- 랜덤 suffix/file name 사용하기
- OCR 텍스트를 사람이 읽기 좋게 임의 교정하기
- 테스트 없이 heuristic 만 추가하기

### 권장

- 작은 단위로 구현하고 자주 테스트할 것
- TODO 와 limitation 을 명확히 남길 것
- baseline 을 깨는 변경이면 golden diff 를 확인할 것
- 실험 기능은 opt-in 으로 둘 것

---

## 12. 커밋/작업 보고 규칙

Codex는 작업 단위를 작게 유지하고, 각 단계에서 아래 내용을 요약해야 한다.

- 구현한 기능
- 수정한 파일
- 추가/수정한 테스트
- 남은 제한사항
- 다음 권장 작업

가능하면 한 커밋이 한 작업(Txx)과 대응되게 유지한다.

---

## 13. 완료 정의

아래 조건을 만족하면 v1 P0 완료로 간주한다.

- CLI 입력으로 `document.md` 생성
- 텍스트 원문 보존 중심 추출 가능
- 단순 표 GFM 출력 가능
- 이미지 referenced 출력 가능
- OCR 기본 지원 가능
- `manifest.json`, `report.json` 생성 가능
- 부분 실패 종료 코드 2 지원 가능
- 핵심 fixture/golden tests 통과

---

## 14. 한 줄 지침

애매하면 더 보수적으로 구현한다.

즉,

- 텍스트는 그대로
- 표는 안전하게
- 이미지는 참조로
- 실패는 기록하고 계속 진행

