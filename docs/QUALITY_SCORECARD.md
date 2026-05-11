# Project Quality Scorecard

이 문서는 프로젝트의 성능, 완성도, 운영 준비도를 주기적으로 평가하고 히스토리로 남기기 위한 기록 문서다.

## 운영 규칙

- 평가는 보수적으로 수행한다. 기능이 “있다”보다 실제 PDF에서 반복 검증되고 회귀 방어가 가능한지를 더 중요하게 본다.
- 새 평가를 수행할 때마다 `평가 히스토리`에 새 항목을 추가한다.
- 기존 평가 항목은 삭제하지 않는다. 과거 판단과 점수 변화 흐름을 추적하기 위함이다.
- 앞으로 구현할 작업은 이 문서에 backlog로 관리하지 않는다. 실제 다음 작업은 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에만 기록한다.
- 평가 후 새로 발견한 개선 과제가 있으면 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 추가하고, 이 문서에서는 해당 Q 번호만 참조한다.
- 점수 기준이나 가중치를 바꾸는 경우, 해당 평가 항목에 변경 이유를 남긴다.

## 평가 기준

총점은 100점 만점이며, 다음 항목을 기준으로 한다.

| 항목 | 배점 | 평가 관점 |
|---|---:|---|
| 핵심 변환 완성도 | 18 | text/table/image/OCR/manifest/report/partial success의 실제 동작 안정성 |
| 표 변환/RAG 대응 | 18 | 단순 표 GFM, 복잡 표 HTML fallback, RAG sidecar, table diagnostics 품질 |
| 텍스트 구조 보존 | 16 | reading order, heading/list/code/footnote, hyphenation, 원문 보존 안정성 |
| 이미지/OCR 신뢰도 | 14 | referenced image, dedupe, crop fallback, OCR runtime/language 진단 |
| 성능/효율 | 12 | page cache, 중복 open 방지, stage duration, benchmark와 회귀 감지 |
| 테스트/결정성/CI | 12 | unit/integration/golden/CLI smoke/CI matrix/결정적 출력 |
| 운영/릴리스 준비도 | 10 | 문서, schema 계약, 배포 smoke, 릴리스 전 품질 게이트 |

배점 합은 100점이며, 항목별 점수 합계를 현재 평가 총점으로 기록한다.

## 평가 히스토리

### 2026-05-11

#### 총평

현재 프로젝트는 **85/100점** 수준으로 평가한다.

기능 수와 테스트 상태만 보면 더 높게 볼 수도 있지만, 실제 PDF corpus 기준의 정량 품질 게이트, 성능 회귀 기준선, 출력 schema/패키징 릴리스 계약이 아직 완성되지 않았으므로 90점대 평가는 보류한다.

#### 세부 점수

| 항목 | 점수 | 평가 |
|---|---:|---|
| 핵심 변환 완성도 | 16/18 | text/table/image/OCR/manifest/report/partial success가 갖춰져 있고 기본 동작은 안정적이다. |
| 표 변환/RAG 대응 | 15/18 | HTML fallback 정책과 RAG sidecar가 좋다. 실문서 복잡 표 calibration은 더 필요하다. |
| 텍스트 구조 보존 | 12/16 | 보수적 heading/list/code/hyphenation은 있다. font/geometry 기반 판단은 아직 다음 단계다. |
| 이미지/OCR 신뢰도 | 12/14 | image dedupe, crop fallback, OCR lang 진단이 있다. crop 시각 검증과 OCR preflight는 미완이다. |
| 성능/효율 | 10/12 | page cache, stage duration, benchmark script는 있다. 성능 regression gate는 아직 없다. |
| 테스트/결정성/CI | 12/12 | `92 passed`, golden corpus, GitHub Actions Python 3.11/3.14까지 양호하다. |
| 운영/릴리스 준비도 | 8/10 | README/Windows guide는 좋다. schema 계약, wheel 패키징 smoke, release gate가 더 필요하다. |

#### 장점

- 기본 변환 정책이 보수적이다. 복잡 표를 억지로 GFM으로 만들지 않고 HTML fallback과 RAG sidecar를 분리했다.
- `manifest.json`, `report.json`, page-level diagnostics, debug artifacts가 있어 재처리와 분석이 가능하다.
- synthetic golden corpus와 CI가 있어 회귀 방어력이 올라갔다.
- `PdfDocumentContext`, page cache, `stage_durations_ms`, benchmark script가 있어 성능을 추적할 기반이 있다.
- 새 기능 대부분이 opt-in이라 기본 출력 호환성을 크게 흔들지 않는다.

#### 단점

- 실제 PDF corpus 품질을 threshold로 막는 게이트가 아직 없다.
- OCR은 runtime/language 환경 의존성이 커서 사전 점검 도구가 필요하다.
- figure crop fallback은 opt-in으로 안전하지만, blank crop이나 잘못된 영역 검증은 부족하다.
- multi-page table continuation은 기본 metadata가 있으나 오탐 방지용 calibration fixture가 더 필요하다.
- 출력 schema와 패키징 릴리스 계약이 아직 별도 문서/테스트로 고정되어 있지 않다.

#### 다음 개선 참조

현재 평가에서 확인된 주요 개선 과제는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 다음 항목으로 반영되어 있다.

- Q01. 실문서 Corpus 품질 게이트 고도화
- Q02. Font/Geometry 기반 텍스트 블록 구조화
- Q03. Figure Crop Fallback 시각 검증 및 보정
- Q04. Multi-page Table Continuation 보정
- Q05. OCR Runtime/Language 사전 점검
- Q06. Benchmark 성능 회귀 게이트
- Q07. Output Schema / 패키징 릴리스 계약

#### 검증 기준

이 평가 시점의 확인 결과는 다음과 같다.

- `./.venv311/bin/python -m pytest`: `92 passed`
- `./.venv311/bin/python -m pdf2md --help`: 정상
- GitHub Actions CI: Python 3.11, 3.14 통과
