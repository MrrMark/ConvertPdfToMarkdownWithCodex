# tasks.md

## 문서 목적

이 문서는 `PRD_pdf_to_markdown_converter.md`를 구현 가능한 작업 단위로 분해한 실행 계획서다.
GPT Codex는 이 문서를 기준으로 작업을 **작게 쪼개고, 순서대로 구현하고, 각 단계마다 테스트를 통과**시켜야 한다.

본 프로젝트의 핵심 원칙은 아래 한 줄이다.

> 텍스트는 그대로, 표는 안전하게, 이미지는 외부 파일 참조로, 애매하면 보수적으로 fallback 한다.

---

## 0. 공통 작업 원칙

- 모든 구현은 **작동하는 최소 버전**부터 시작한다.
- 한 번에 큰 리팩터링을 하지 말고, **CLI → pipeline → extractor/serializer 분리** 순서로 진행한다.
- 테이블은 **잘못된 GFM 표보다 HTML fallback** 이 우선이다.
- 이미지는 기본적으로 **referenced mode** 로 구현한다.
- AI/VLM 기반 이미지 설명은 **off-by-default** 로만 구현한다.
- 실패가 있어도 가능한 경우 **partial success** 를 유지해야 한다.
- 같은 입력 + 같은 옵션이면 **동일한 출력 파일명/내용** 이 나와야 한다.
- 각 작업 완료 시점마다 최소한 아래를 확인한다.
  - CLI 실행 가능 여부
  - 테스트 통과 여부
  - golden output diff 확인 여부
  - `manifest.json`, `report.json` 스키마 유효성

---

## 1. 목표 릴리스 범위

### v1 P0

반드시 먼저 끝내야 하는 범위:

- 단일 PDF 입력 CLI
- 텍스트 추출
- 단순 표 GFM 출력
- 이미지 referenced 출력
- OCR 기본 지원
- `manifest.json` / `report.json` 생성
- 부분 실패 처리 및 종료 코드 구분

### v1 P1

P0 안정화 후 구현:

- 복잡 표 HTML fallback 고도화
- 멀티컬럼 문서 reading order 개선
- header/footer 제거 옵션
- page marker on/off 옵션
- image dedupe

### v1 P2

선택 확장:

- 이미지 설명 생성 옵션
- PyMuPDF / Docling adapter
- appendix / comment / json 이미지 설명 출력 모드
- figure/table caption confidence 모델 고도화

---

## 2. 권장 구현 순서

1. 프로젝트 골격 생성
2. CLI 진입점 생성
3. 설정/스키마 모델 생성
4. 최소 텍스트 추출 파이프라인 구현
5. Markdown serializer 구현
6. manifest/report 생성
7. 이미지 추출 및 상대경로 연결
8. 단순 표 GFM serializer 구현
9. OCR pipeline 연결
10. 오류 처리 / partial success / 종료 코드
11. 테스트 fixture / golden test 구축
12. P1/P2 기능 확장

---

## 3. 작업 백로그

---

## T00. 프로젝트 초기 구조 생성

### 목표

PRD 기준의 기본 디렉터리와 패키지 구조를 만든다.

### 세부 작업

- 아래 구조를 기준으로 초기 scaffold 생성

```text
pdf2md/
  __init__.py
  cli.py
  config.py
  models.py
  pipeline.py
  detectors/
  extractors/
  serializers/
  utils/
  tests/
    fixtures/
    golden/
```

- 패키지 import 경로가 일관되게 동작하도록 정리
- `pyproject.toml` 또는 동등한 패키지 설정 추가
- 실행 엔트리포인트 `pdf2md` 등록

### 완료 조건

- `python -m pdf2md --help` 또는 `pdf2md --help` 가 동작한다.
- 프로젝트가 import error 없이 로드된다.

---

## T01. CLI 기본 골격 구현

### 목표

최소 실행 가능한 CLI를 만든다.

### 세부 작업

- 아래 옵션을 우선 구현
  - `INPUT_PDF`
  - `-o, --output-dir`
  - `--pages`
  - `--password`
  - `--image-mode`
  - `--table-mode`
  - `--force-ocr`
  - `--keep-page-markers / --no-page-markers`
  - `--debug`
  - `--verbose`
- 아직 미구현 옵션은 placeholder 대신 TODO와 명확한 에러 메시지 제공
- 종료 코드 정책 뼈대 추가

### 완료 조건

- 도움말이 PRD 옵션과 크게 어긋나지 않는다.
- 잘못된 옵션 입력 시 명확한 오류 메시지를 반환한다.

---

## T02. 설정 및 데이터 모델 정의

### 목표

실행 옵션과 출력 메타데이터를 구조화한다.

### 세부 작업

- `Config` 모델 정의
- `Manifest`, `Report`, `ImageAsset`, `TableAsset`, `PageResult`, `WarningEntry` 등 Pydantic 모델 정의
- JSON serialization 규칙 고정
- enum 정의
  - `ImageMode = referenced | embedded | placeholder`
  - `TableMode = auto | gfm-only | html-only`

### 완료 조건

- config/model 단위 테스트가 존재한다.
- `manifest.json`, `report.json` 예제 직렬화가 가능하다.

---

## T03. PDF 입력/페이지 로딩 레이어 구현

### 목표

PDF 열기, 페이지 접근, 페이지 범위 선택, 비밀번호 처리 기반을 만든다.

### 세부 작업

- `pypdf` 로 PDF 로딩
- 비밀번호 처리
- 페이지 범위 파서 구현
  - 예: `1-3,5,7-9`
- 잘못된 페이지 범위 처리
- 총 페이지 수 계산

### 완료 조건

- 페이지 선택이 deterministic 하게 동작한다.
- 비밀번호 없는 PDF/비밀번호 PDF 테스트가 있다.

---

## T04. 최소 텍스트 추출기 구현

### 목표

디지털 PDF에서 본문 텍스트를 원문 중심으로 추출한다.

### 세부 작업

- `pdfplumber` 기반 페이지별 텍스트 추출 구현
- reading order 기본 복원
- 빈 페이지/텍스트 없는 페이지 처리
- 의미 없는 줄바꿈 최소 정리
- NFC normalization 적용
- 옵션 기반 하이픈 복구 훅 추가

### 완료 조건

- 일반 단일 컬럼 PDF에서 문단 텍스트가 추출된다.
- 텍스트를 요약/교정하지 않는다.
- golden test 1개 이상 추가

---

## T05. 기본 Markdown serializer 구현

### 목표

텍스트 블록을 Markdown으로 직렬화한다.

### 세부 작업

- page marker 출력 옵션 구현
- paragraph serializer 구현
- heading 후보/일반 paragraph 구분의 최소 규칙 추가
- list 후보 처리의 최소 규칙 추가
- 안전한 line break 정책 구현

### 완료 조건

- `document.md` 가 생성된다.
- page marker on/off 가 동작한다.
- golden markdown snapshot 테스트가 있다.

---

## T06. manifest.json / report.json 생성

### 목표

실행 결과를 재처리 가능한 메타데이터로 남긴다.

### 세부 작업

- 입력 파일명, 총 페이지 수, 옵션 기록
- 처리 시간, warning, failure, OCR 적용 페이지 기록
- 페이지별 summary statistics 기록
- 추출 엔진 사용 여부 기록

### 완료 조건

- `manifest.json`, `report.json` 가 항상 생성된다.
- 부분 실패 시에도 가능한 범위까지 기록된다.

---

## T07. 이미지 추출 - referenced mode 구현

### 목표

이미지를 파일로 추출하고 Markdown에 상대경로로 연결한다.

### 세부 작업

- embedded raster image 우선 추출
- `assets/images/` 저장 규칙 구현
- 파일명 규칙 구현
  - `page-0002-figure-001.png`
- 문서 내 상대경로 링크 삽입
- alt text 기본 규칙 구현
- 캡션 후보 연결의 최소 규칙 구현
- bbox / width / height / sha256 기록

### 완료 조건

- 이미지가 파일로 저장된다.
- Markdown에서 상대경로가 깨지지 않는다.
- manifest 에 이미지 메타데이터가 남는다.

---

## T08. 단순 표 추출 + GFM serializer 구현

### 목표

단순 구조 표를 GFM pipe table로 출력한다.

### 세부 작업

- `pdfplumber` 기반 테이블 추출
- 직사각형 구조 복원 검사
- 헤더 행 처리
- 셀 텍스트 sanitize
  - `|` escape
  - 줄바꿈 정리
- GFM 가능 여부 판정 함수 구현
- 표 메타주석 삽입

### 완료 조건

- 단순 표 fixture 에서 GFM 표가 생성된다.
- 잘못된 구조의 표를 억지로 GFM 으로 만들지 않는다.

---

## T09. 복잡 표 HTML fallback 구현

### 목표

복잡 표를 안전하게 HTML table 로 출력한다.

### 세부 작업

- rowspan / colspan / multi-header / multi-paragraph cell 여부 판정
- `table-mode=auto` 시 HTML fallback 로직 구현
- `table-mode=gfm-only` 시 fallback warning 처리 정책 구현
- `table-mode=html-only` 시 모든 표를 HTML 로 내보내기
- 표 caption 연결 규칙의 최소 버전 추가

### 완료 조건

- 병합 셀/복잡 표 fixture 에서 HTML table 이 생성된다.
- report 에 fallback 사유가 기록된다.

---

## T10. OCR 파이프라인 구현

### 목표

스캔 PDF 또는 텍스트 레이어가 불충분한 페이지를 OCR 처리한다.

### 세부 작업

- 텍스트 레이어 유무 감지
- `--force-ocr` 처리
- 페이지 단위 OCR 실행
- OCR confidence 낮은 경우 warning 기록
- OCR 결과를 기존 Markdown serializer 로 연결

### 완료 조건

- 스캔 PDF fixture 에서 본문이 추출된다.
- 자동 OCR 또는 강제 OCR 중 최소 하나는 신뢰성 있게 동작한다.

---

## T11. 오류 처리 / partial success / 종료 코드 구현

### 목표

실패해도 가능한 산출물을 남기는 안정적 실행 흐름을 완성한다.

### 세부 작업

- 페이지 단위 예외 격리
- 이미지/표/OCR 실패를 개별 warning 으로 기록
- 문서 전체 치명적 실패와 부분 성공 구분
- 종료 코드 구현
  - `0`: 성공
  - `1`: 치명적 실패
  - `2`: 부분 성공
- 실패 placeholder/comment 삽입 정책 구현

### 완료 조건

- 일부 페이지 실패 테스트가 존재한다.
- 전체 실행이 중단되지 않고 report 에 기록된다.

---

## T12. 테스트 fixture 및 golden regression 구축

### 목표

반복 구현 중 회귀를 잡을 수 있는 테스트 체계를 만든다.

### 세부 작업

- fixture PDF 수집/추가
  - 일반 단일 컬럼
  - 멀티컬럼
  - 단순 표
  - 복잡 표
  - 이미지 다수
  - 스캔 PDF
  - 한글 PDF
  - 영문 PDF
  - 비밀번호 PDF
- golden markdown / manifest / report 저장
- CLI smoke test 추가
- schema validation test 추가

### 완료 조건

- 최소 P0 전 범위에 대한 regression test 가 있다.
- 테스트 명령 1회로 핵심 회귀를 확인할 수 있다.

---

## T13. 멀티컬럼 reading order 개선

### 목표

P1 기능으로 멀티컬럼 문서의 텍스트 순서를 개선한다.

### 세부 작업

- 페이지 블록 좌표 기반 컬럼 분리 후보 탐지
- 좌→우 / 상→하 읽기 순서 정책 실험
- 오검출을 줄이는 보수적 heuristic 적용
- 실패 시 단일 컬럼 fallback 유지

### 완료 조건

- 멀티컬럼 fixture 에서 baseline 대비 품질이 개선된다.
- 잘못된 재배열보다 보수적 fallback 이 우선된다.

---

## T14. header/footer 제거 옵션 구현

### 목표

반복 머리말/꼬리말을 옵션으로 제거한다.

### 세부 작업

- 페이지 간 반복 텍스트 패턴 탐지
- 상단/하단 bbox 기반 후보 탐지
- `--remove-header-footer` 옵션 연결
- 과도 제거 방지 로직 구현

### 완료 조건

- 반복 header/footer 가 있는 fixture 에서 제거된다.
- 본문 오제거에 대한 방지 테스트가 있다.

---

## T15. image dedupe 구현

### 목표

같은 이미지가 반복 삽입된 경우 중복 저장을 줄인다.

### 세부 작업

- sha256 기반 hash 계산
- `--dedupe-images` 옵션 구현
- 중복 asset 재사용 규칙 구현
- manifest 에 원본 위치 매핑 유지

### 완료 조건

- 동일 이미지 반복 문서에서 asset 수가 줄어든다.
- Markdown 링크와 manifest 정보는 유지된다.

---

## T16. debug artifact 저장 기능 구현

### 목표

문제 추적을 위한 중간 산출물 저장 기능을 제공한다.

### 세부 작업

- `--debug` 시 페이지별 intermediate dump 저장
- 예: extracted text, table raw JSON, image crop, OCR raw text
- debug 산출물 디렉터리 구조 정의

### 완료 조건

- 디버그 모드에서만 추가 파일이 생성된다.
- 일반 모드 결과물은 과도하게 오염되지 않는다.

---

## T17. 이미지 설명 선택 기능 구현

### 목표

P2 기능으로 이미지 설명 생성 옵션을 추가한다.

### 세부 작업

- 기본값은 비활성화 유지
- `--describe-images` 와 output mode 구현
  - `comment`
  - `json`
  - `appendix`
- 본문 원문을 오염시키지 않도록 sidecar 우선
- 설명 생성 실패 시 전체 변환 실패로 취급하지 않음

### 완료 조건

- 기능이 off-by-default 로 유지된다.
- 기본 출력물에는 환각 텍스트가 들어가지 않는다.

---

## T18. PyMuPDF / Docling adapter 실험

### 목표

P2 기능으로 대체 추출 백엔드를 실험적으로 추가한다.

### 세부 작업

- adapter 인터페이스 정의
- `pdfplumber` 기본 백엔드는 유지
- 실험용 backend switch 옵션 추가
- 결과 품질 및 성능 비교용 benchmark 추가

### 완료 조건

- 기본 backend 동작을 깨지 않는다.
- 실험 backend 는 opt-in 이어야 한다.

---

## T19. README / examples / 운영 문서 보강

### 목표

실사용 가능한 개발자 문서를 완성한다.

### 세부 작업

- 설치 방법
- 시스템 요구사항
- OCR/Tesseract 설치 안내
- 기본 CLI 예시
- 옵션별 예시
- known limitations
- sample output 구조 설명

### 완료 조건

- 새 개발자가 README 만 보고 실행할 수 있다.

---

## 4. 작업 간 의존성

- T00 → T01 → T02 → T03 → T04 → T05 → T06 이 기본 선행 흐름이다.
- T07, T08, T10 은 T03 이후 병렬 가능하다.
- T09 는 T08 이후 진행한다.
- T11 은 T04~T10 이후 통합한다.
- T12 는 가능한 빨리 시작하되, 최소한 T05 시점부터 golden test 를 누적한다.
- T13~T18 은 P0 안정화 후 진행한다.

---

## 5. P0 완료 정의

아래가 모두 만족되면 P0 완료로 판단한다.

- CLI로 PDF 입력 시 `document.md` 생성
- 일반 디지털 PDF 텍스트 추출 가능
- 단순 표 GFM 출력 가능
- 이미지 referenced 출력 가능
- OCR 기본 동작 가능
- `manifest.json`, `report.json` 생성
- 부분 실패 시 종료 코드 2 반환 가능
- 최소 fixture/golden test 세트 통과

---

## 6. Codex 실행 지침

Codex는 아래 순서를 기본으로 따른다.

1. 먼저 T00~T06 까지 끝내서 **텍스트 중심 최소 제품**을 만든다.
2. 그 다음 T07~T11 로 **실사용 가능한 P0** 를 완성한다.
3. 테스트를 먼저 보강한 뒤 P1/P2 기능을 진행한다.
4. 각 단계마다 작은 단위로 커밋하고, 작업 요약에는 아래를 반드시 포함한다.
   - 무엇을 구현했는지
   - 어떤 테스트를 추가/수정했는지
   - 남은 제한사항이 무엇인지

---

## 7. 하지 말아야 할 것

- OCR 결과를 멋대로 교정/의역하지 말 것
- 복잡 표를 억지로 GFM 표로 만들지 말 것
- 이미지 설명을 기본 본문에 강제로 삽입하지 말 것
- 실패 시 전체 결과물을 버리지 말 것
- deterministic output 을 깨는 랜덤 suffix/file name 을 쓰지 말 것
- README 없이 구현만 남기지 말 것

