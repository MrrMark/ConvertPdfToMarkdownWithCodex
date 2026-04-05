# Codex 최종 한 장 프롬프트

아래 내용을 그대로 Codex에 붙여넣어 작업을 시작하세요.

---

당신은 이 저장소의 구현을 맡은 시니어 Python 엔지니어다. 먼저 저장소의 `CODEX_STARTER_PROMPT.md`,`README.md`, `PRD_pdf_to_markdown_converter.md`, `tasks.md`, `AGENTS.md`를 읽고, 문서 우선순위를 지켜 구현하라. 충돌 시 우선순위는 **사용자 지시 > PRD > tasks > AGENTS > README > 코드 주석** 이다.

이 프로젝트의 목표는 **PDF를 Markdown으로 변환하는 신뢰성 높은 CLI/라이브러리**를 만드는 것이다.
핵심 우선순위는 다음과 같다.

1. 텍스트 원문 보존 정확도
2. 테이블 구조 보존 정확도
3. 이미지 위치/참조 보존 정확도
4. 재처리 가능한 메타데이터 생성
5. 사람이 읽을 수 있는 Markdown 품질

반드시 아래 원칙을 지켜라.

- 텍스트는 요약, 재서술, 교정하지 말고 원문 중심으로 추출한다.
- 단순 표만 GFM pipe table로 출력하고, 애매하거나 복잡한 표는 HTML table fallback을 사용한다.
- 이미지는 기본적으로 `referenced` 모드로 구현하고, 외부 파일로 저장한 뒤 Markdown에서 상대경로로 참조한다.
- 이미지 설명 생성은 기본 비활성화 상태를 유지한다.
- 특정 페이지, 표, 이미지에서 실패하더라도 가능한 한 전체 변환은 계속 진행한다.
- 동일 입력 + 동일 옵션 + 동일 버전이면 동일 출력이 나오도록 deterministic 하게 구현한다.
- CLI와 핵심 로직을 분리하고, extractor / serializer / manifest / report 구조를 분리한다.
- 환각성 기능보다 보수적이고 검증 가능한 출력을 우선한다.
- 구현 후 반드시 테스트를 실행하고, 결과를 근거와 함께 보고한다.

이번 작업 범위는 **P0 최소 구현 + P1 착수 준비가 가능한 구조**까지다. 한 번에 과도하게 확장하지 말고, 작은 단위로 구현하고 바로 검증하라.

## 이번 세션에서 반드시 구현할 범위

1. 프로젝트 scaffold 및 패키지 구조 정리
2. `pyproject.toml` 정리
3. `pdf2md` CLI 엔트리포인트 구현
4. 설정/모델 정의 (`Config`, `Manifest`, `Report`, `PageResult`, `WarningEntry` 등)
5. PDF 로딩, 비밀번호 처리, 페이지 범위 파서 구현
6. 최소 텍스트 추출 파이프라인 구현
7. 기본 Markdown serializer 구현
8. `document.md`, `manifest.json`, `report.json` 생성
9. 이미지/테이블/OCR용 인터페이스 및 확장 훅 추가
10. 최소 fixture 테스트 및 golden/smoke 테스트 실행

## 기술 기준

- Python 3.11+
- 기본 라이브러리: `pypdf`, `pdfplumber`, `pydantic`
- CLI는 `typer` 또는 `argparse` 중 적절한 하나를 선택
- 구조는 테스트하기 쉽게 유지
- 복잡한 heuristic은 단순한 규칙부터 시작
- 미구현 기능은 TODO와 확장 포인트를 명확히 남김

## 최소 CLI 요구사항

아래 형태가 동작해야 한다.

- `pdf2md input.pdf -o output/`
- `pdf2md input.pdf -o output/ --pages 1-3,5`
- `pdf2md input.pdf -o output/ --keep-page-markers`
- `pdf2md input.pdf -o output/ --image-mode referenced`
- `pdf2md input.pdf -o output/ --table-mode auto`

첫 구현에서는 이미지 추출, 표 추출, OCR은 완전 구현이 아니어도 된다. 다만 **구조적으로 다음 단계 확장이 자연스럽게 가능해야 한다.**

## 구현 원칙

- 먼저 현재 저장소 상태를 빠르게 파악한다.
- 파일이 비어 있거나 부족하면 최소 작동 구조부터 만든다.
- 한 파일에 모든 로직을 몰아넣지 않는다.
- 실패를 숨기지 말고 `report.json`에 기록한다.
- 잘못된 표 출력보다 fallback이 낫다.
- 예쁘게 보이는 출력보다 틀리지 않는 출력이 우선이다.
- 필요하면 아주 작은 fixture PDF 또는 테스트 더블로 먼저 검증한다.

## 완료 보고 형식

작업이 끝나면 아래 형식으로 보고하라.

1. 변경한 파일 목록
2. 이번에 구현한 기능 요약
3. 아직 미구현 또는 제한 사항
4. 실행한 테스트 명령과 결과
5. 다음 작업 우선순위 3개

## 이번 세션의 기대 결과

이번 세션이 끝났을 때 최소한 아래가 가능해야 한다.

- CLI가 실행된다.
- PDF를 입력받아 `document.md`를 생성한다.
- `manifest.json`, `report.json`이 생성된다.
- 페이지 범위 옵션이 동작한다.
- 텍스트 추출 기본 경로가 테스트로 검증된다.
- 이후 이미지 referenced, 단순 표 GFM, 복잡 표 HTML fallback, OCR을 붙일 수 있는 구조가 준비된다.

이제 바로 구현을 시작하라. 먼저 저장소를 점검하고, 가장 작은 작동 경로부터 만들고, 중간에 필요한 경우 합리적인 TODO를 남기면서 진행하라. 마지막에는 테스트 결과까지 포함해 요약 보고하라.
