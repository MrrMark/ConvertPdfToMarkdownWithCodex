# Quality Improvement Development Specs

이 문서는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 남아 있는 **active Q 작업**을 실제 구현 PR로 옮기기 위한 개발 명세다.

완료된 Q 작업의 명세와 구현 결과는 이 문서에 남기지 않고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 관리한다.

## 운영 규칙

- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 신규 Q 항목이 추가되면, 구현 전에 이 문서에 대응 개발 명세를 작성한다.
- 구현 중 범위가 바뀌면 Next Plan 항목과 이 문서를 함께 갱신한다.
- 구현 완료, 테스트 통과, PR merge까지 끝난 Q 항목은 이 문서에서 제거하고 완료 명세 archive로 옮긴다.
- 완료 이력은 Git commit, PR, release note, changelog, 그리고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 추적한다.
- 이 문서에는 앞으로 구현할 active 명세만 있어야 한다.

## 공통 원칙

- 외부 RAG/indexing 서비스 호출은 구현 범위에 포함하지 않는다.
- 모든 검증과 fixture 생성은 local-only, deterministic 동작을 기본으로 한다.
- PDF 원문 텍스트, 표, 이미지 provenance는 요약하거나 재서술하지 않는다.
- 새 public JSON 출력이 생기면 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/` 계약을 함께 갱신한다.
- 실패는 가능한 한 구조화된 report로 남기고, 어느 파일/record/field/page가 문제인지 식별 가능해야 한다.
- 테스트는 작은 unit test, script smoke test, golden regression test를 우선한다.

## 현재 Active Development Specs

### 실행 조건

- 로컬 CPU를 기준으로 Mac과 Windows를 지원한다. GPU·클라우드 업로드는 필수 조건이 아니다.
- 검증된 수정은 기존 기본 동작에 반영한다. 파일명·기존 필드를 유지하고 메타데이터는 추가 방식으로 확장한다.
- 비교 도구는 별도 실험 환경에서 사용하며 제품 런타임 의존성으로 추가하지 않는다.
- 각 Q 작업의 회귀 검사를 먼저 작성하고, 변경 후 unit/integration/CLI/golden 검사를 실행한다.
- 기존 무결성 검사 통과를 원문 품질 통과로 해석하지 않는다.

### Q154. 빈 표 억제 및 벡터 도식 보존

셀 내용과 경계를 함께 검사하여 전부 빈 표를 확정 단계에서 제외하고 진단을 남긴다. 표 제외만으로 도식으로 승격하지 않는다. 원문 캡션과 도형 증거가 있는 경우 기존 crop 로직을 활용한다.

- 확정된 실제 표와 겹치는 Figure 캡션은 crop에서 제외한다.
- crop 성공 시 도식 내부 조각난 텍스트를 일반 본문에서 제거하되 figure evidence로 보존한다. 실패·불확실 시 원문 유지와 warning을 우선한다.
- 최종 빈 HTML 표는 fallback 여부와 무관하게 integrity 오류로 처리한다.
- 검증: controller 페이지 3의 빈 표 4개 제거와 도식 3개 보존, 페이지 4 실제 표 3개 유지, SGL 표 유지.

2026-09-14 구현 및 로컬 검증 완료. 구현 범위·실제 문서 결과·제한사항은
[Q154 구현 결과](Q154_VECTOR_FIGURE_IMPLEMENTATION.md)에 기록한다. PR merge까지 이 항목을 유지한다.

### Q155. 중첩 표 구조 보존

내부 셀 모델은 row/column/span/bbox/raw text/children을 가진다. 단순 bbox 겹침이 아닌 경계와 포함 관계로 중첩을 판정한다.

- 부모 `<td>` 내부에 실제 HTML `<table>`을 직렬화하고 병합 셀은 HTML로 보존한다.
- `TableAsset.cell_structure` 및 선택적 row `cell_refs`를 추가한다. 기존 cells/row_text/최상위 table ID를 유지한다.
- 자식 ID는 부모 ID와 구조 위치에서 결정한다. 자식 표를 별도의 동일 검색 청크로 중복 생성하지 않는다.
- 확정 불가 시 원문 fallback과 actionable `structure_loss`를 기록한다.
- 검증: Figure 118/119 byte 15 안의 07:04/03:00 중첩 관계, 단순 표 불변, 순환·누락·중복 방지.

2026-09-14 구현 및 로컬 검증 완료. [Q155 구현 결과](Q155_NESTED_TABLE_IMPLEMENTATION.md)에
원문 품질·회귀 결과와 화면 검증 제한을 기록한다. PR merge까지 이 항목을 유지한다.

### Q156. 비교 벤치마크 공정성

동일 slice를 독립 프로세스에서 처리한다. native 유효 CLI 옵션을 기록하고 Docling의 실제 document 객체에서 표·그림 수를 센다.

- input hash, 패키지/모델 버전, worker/thread, peak RSS를 기록한다.
- import·설정·모델 다운로드와 convert+export/write를 분리한다.
- cold 1회와 warm 5회의 중앙값 및 범위를 사용한다. 소표본 p95는 보고하지 않는다.
- 원문 품질, 처리량, 기능 지원을 분리하며 미지원 기능을 품질 0점으로 환산하지 않는다.

### Q157. 외부 CPU 도구 비교 실험

별도 환경에 Docling 2.126, Marker 2.0 fast, PyMuPDF4LLM 1.27.2.2를 고정하여 Q152 corpus를 비교한다. 각 버전 설치 가능 여부부터 확인하고 정확한 패치 버전을 실행 기록에 남긴다.

- 원본은 로컬에서만 파싱하고 모델 다운로드는 계측에서 제외한다.
- 설치·실행 불가 시 사유를 기록한다. 임의 버전 변경 또는 클라우드 대체 실행은 하지 않는다.
- MinerU/Paddle VLM/GPU는 필수 비교에서 제외한다. 결과는 향후 채택 판단용이며 제품 backend 통합은 별도 작업이다.

### Q158. 한글 검색 평가 및 회귀 마감

기존 lexical smoke를 유지하고 Unicode 단어·기술 식별자·한글 문자 bigram 기반 로컬 BM25 기준선을 추가한다.

- 사람이 검토한 한글 15개·영어 15개 질문에 requirement/table/figure 원문 참조를 부여한다.
- Recall@5, MRR@5, citation 및 중요 토큰 보존을 평가한다. embedding/reranker/LLM 평가는 범위 밖이다.
- 로컬 Mac, Windows CPU CI, 기존 Linux CI를 검증한다.
- 전체 회귀와 release gate를 실행하고 원문 품질과 내부 무결성 결과를 각각 보고한다.

### Q159. Visual sidecar 참조 계약 검증

Q153 실측 중 이전 버전부터 존재하던 visual 계약 오류를 발견했다. front matter 462건, controller 22건이며 수정 전후 finding 목록은 동일하다.

- 실제 source reference의 `figure`/`excluded_figure` 타입과 ID를 확인하고 생산자·검증기 중 어느 계약이 잘못됐는지 재현 fixture로 구분한다.
- description/OCR evidence/structure의 정당한 참조를 수용하되 실제 누락·잘못된 target ID 검출은 유지한다.
- 실제 레코드 삭제나 검사 생략으로 오류를 숨기지 않는다.
- 합성 정상/실패 회귀 검사와 기존 실제 두 사례의 오류 해소를 완료 기준으로 삼는다. Q153에서는 수정하지 않는다.

## 완료 명세 Archive

완료된 Q34-Q153 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
