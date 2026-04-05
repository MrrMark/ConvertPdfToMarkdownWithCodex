# Codex Starter Prompt

아래 프롬프트는 이 프로젝트를 **실제로 구현 시작할 때 바로 Codex에 붙여넣을 수 있는 스타터 프롬프트**입니다.

---

## Prompt

당신은 이 저장소의 구현을 맡은 시니어 Python 엔지니어다.

우선 이 저장소의 아래 문서를 모두 읽고, 문서 간 우선순위를 지켜서 구현을 시작해라.

1. `PRD_pdf_to_markdown_converter.md`
2. `tasks.md`
3. `AGENTS.md`
4. `README.md`

이 프로젝트의 목표는 **PDF를 Markdown으로 변환하는 신뢰성 높은 CLI/라이브러리**를 만드는 것이다.
가장 중요한 우선순위는 아래와 같다.

1. 텍스트 원문 보존 정확도
2. 테이블 구조 보존 정확도
3. 이미지 위치/참조 보존 정확도
4. 재처리 가능한 메타데이터 생성
5. 사람이 읽을 수 있는 수준의 Markdown 품질

반드시 아래 원칙을 지켜라.

- 텍스트를 요약, 재서술, 교정하지 마라.
- 단순 표만 GFM pipe table로 출력해라.
- 표가 애매하거나 복잡하면 HTML table fallback을 사용해라.
- 이미지는 기본적으로 `referenced` 모드로 구현해라.
- 이미지 설명 생성은 기본 비활성화로 유지해라.
- 특정 페이지/표/이미지에서 실패하더라도 전체 변환을 가능한 한 계속 진행해라.
- 같은 입력 + 같은 옵션이면 같은 출력이 나오게 deterministic 하게 구현해라.
- CLI와 순수 로직을 분리해라.
- extractor / serializer / report schema를 분리해라.
- 구현 후 반드시 테스트를 실행하고 결과를 보고해라.

이번 첫 작업의 범위는 **P0 최소 구현**까지다. 한 번에 모든 것을 완성하려고 하지 말고, 아래 순서대로 작게 나눠서 구현해라.

### 이번 작업에서 구현할 범위

1. 프로젝트 scaffold 생성
2. `pyproject.toml` 작성
3. `pdf2md` 패키지 기본 구조 생성
4. CLI 엔트리포인트 구현
5. 설정/모델 정의
6. PDF 로딩 및 페이지 범위 파서 구현
7. 최소 텍스트 추출기 구현
8. 기본 Markdown serializer 구현
9. `manifest.json` / `report.json` 생성
10. 최소 테스트 추가 및 실행

### 우선 구현 대상 세부 요구

- Python 3.11+ 기준
- `pypdf`, `pdfplumber`, `pydantic` 사용
- CLI는 `typer` 또는 `argparse` 중 하나를 선택
- 기본 명령은 아래 형태를 지원
  - `pdf2md input.pdf -o output/`
  - `pdf2md input.pdf -o output/ --pages 1-3,5`
  - `pdf2md input.pdf -o output/ --keep-page-markers`
- 첫 구현에서는 이미지 추출, 테이블 추출, OCR은 **인터페이스/훅 수준까지만 준비**해도 된다. 다만 구조는 이후 확장을 고려해서 설계해라.
- `document.md`, `manifest.json`, `report.json`이 생성되어야 한다.
- 최소 fixture 기반 테스트를 추가해라.

### 권장 패키지 구조

```text
pdf2md/
  __init__.py
  cli.py
  config.py
  models.py
  pipeline.py
  detectors/
  extractors/
    text.py
  serializers/
    markdown.py
    manifest.py
    report.py
  utils/
  tests/
```

필요하면 구조는 조정해도 되지만, 아래 원칙은 유지해라.

- CLI와 핵심 로직 분리
- 설정과 결과 모델 분리
- serializer 분리
- 테스트하기 쉬운 구조 유지

### 구현 방식

- 먼저 저장소 상태를 빠르게 파악해라.
- 아직 파일이 없다면 최소 작동 구조부터 생성해라.
- 너무 큰 파일 하나에 몰아넣지 마라.
- heuristic은 단순하게 시작하고, 과도한 최적화는 하지 마라.
- 미구현 기능은 TODO와 명확한 구조로 남겨라.
- 실패는 숨기지 말고 `report.json`에 기록하는 방향으로 설계해라.

### 완료 후 반드시 수행할 것

1. 변경된 파일 요약
2. 구현한 기능 요약
3. 아직 미구현인 항목 요약
4. 실행한 테스트와 결과 요약
5. 다음 작업 추천 3개 제안

### 작업 스타일

- 작게 구현하고 바로 실행/검증해라.
- 필요하면 fixture PDF를 아주 작은 샘플로 만들어 테스트해라.
- 추정이 필요한 부분은 보수적으로 구현해라.
- “예쁘게 보이는 출력”보다 “틀리지 않는 출력”을 우선해라.

이제 위 원칙대로 저장소를 구현 시작해라.
우선은 P0 최소 구현만 끝내고, 결과를 요약 보고해라.

---

## 추천 사용 방식

Codex에 위 Prompt를 넣은 뒤, 첫 결과가 나오면 다음 순서로 이어가는 것이 좋습니다.

1. 이미지 referenced 추출 추가
2. 단순 표 GFM serializer 추가
3. 복잡 표 HTML fallback 추가
4. OCR 연결
5. golden test 확대
6. header/footer 제거와 reading order 개선

---

## 후속 프롬프트 예시 1 - 이미지/표 확장

이전 작업을 이어서 진행해라.
이번에는 아래 기능만 추가 구현해라.

1. 이미지 referenced 추출
2. 단순 표 GFM serializer
3. 복잡 표 HTML fallback
4. 관련 fixture/test 추가

중요 원칙:

- 이미지는 `assets/images/`에 deterministic 파일명으로 저장
- Markdown에는 상대경로로 참조
- 잘못된 GFM 표보다 HTML fallback 우선
- 실패는 `report.json`에 기록

구현 후 테스트 실행 결과와 남은 한계를 보고해라.

---

## 후속 프롬프트 예시 2 - OCR 확장

이전 작업을 이어서 진행해라.
이번에는 OCR 경로를 구현해라.

요구사항:

- `--force-ocr` 옵션 지원
- 텍스트가 거의 없는 페이지에서 OCR 적용 가능한 구조 추가
- OCR confidence/warning을 `report.json`에 기록
- 디지털 PDF 경로와 OCR 경로를 분리
- fixture/test 추가

구현 후 테스트 실행 결과와 남은 리스크를 요약해라.

---

## 후속 프롬프트 예시 3 - 안정화

이전 구현을 바탕으로 아래 안정화 작업을 수행해라.

1. golden regression test 확대
2. 에러 처리 개선
3. partial success 정책 강화
4. 로그 구조 개선
5. README의 실행 예시와 실제 CLI 동작 일치 여부 점검

변경 내용, 테스트 결과, 남은 기술 부채를 구분해서 보고해라.
