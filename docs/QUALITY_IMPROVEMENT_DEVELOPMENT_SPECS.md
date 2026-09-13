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

### Q152. 원문 기준 품질 평가

입력 PDF SHA-256, slice 페이지와 원본 물리 페이지·인쇄 페이지를 고정한다. NVMe 14페이지의 렌더를 기준으로 사람이 확인한 정답을 로컬에 작성한다. 정답은 변환 산출물에서 자동 생성하지 않는다.

- 별도 평가기는 원문 토큰, 표 셀/중첩 관계, 도식 위치·캡션, 장식 이미지 OCR 낭비를 검사한다.
- finding은 case/check/page/record/type을 식별한다. 입력·정답 오류는 평가 실패로 처리한다.
- 알려진 실패는 check ID 단위로 명시하며 예상하지 못한 실패와 오래된 allowlist 항목은 gate를 실패시킨다. 알려진 실패만 있는 경우에도 원문 품질은 통과로 표시하지 않는다.
- 실제 원문·정답은 `output/`에 보관하고 저장소에는 합성 fixture, 입력 식별 정보, 집계 결과만 보관한다.
- 최소 검출 대상: 장식 후보 154개 OCR, 빈 HTML 표 4개, Figure 729–731 도식 누락, Figure 118/119 중첩 구조 손실.
- 합성 검사는 정상 표·병합/중첩 표·벡터 도식·한영 토큰·읽기 순서·스캔/OCR 증거와 잘못된 평가 입력을 포함한다.

구현 결과(2026-09-13, PR merge 전): `pdf2md/quality_eval.py`, `scripts/evaluate_source_quality.py` 및 입력/보고서 JSON Schema를 추가했다. NVMe 로컬 14페이지의 17개 assertion에서 알려진 실패를 재현했다. 합성 중첩 셀 PDF의 실제 변환 회귀 검사와 평가기 단위 검사를 추가했다. 기존 변환기 동작과 golden은 변경하지 않았다. 실행 방법·범위·제한은 `docs/SOURCE_QUALITY_EVALUATION.md`, 공유 가능한 입력 식별 정보와 집계는 `docs/evaluation/nvme_source_quality_baseline_2026-09-13.json`에 기록했다.

검증 결과: 로컬 Python 3.11에서 전체 530개 테스트(unit/integration/CLI/golden 포함), Ruff, schema `--check`, CLI `--help`가 통과했다. Q152 신규 검사 23개를 포함한다. 실제 문서 평가는 17개 assertion을 재실행하여 기준선 통과·원문 품질 실패를 각각 확인했다. 이 수치는 Q152 완료 시점이며 이후 결과는 각 항목을 따른다.

### Q153. 선택적 영역 OCR 및 렌더 재사용

Q152 기준선이 고정된 뒤 `TINY_DECORATIVE`로 이미 제외된 후보만 OCR에서 제외한다. 제외된 레코드와 provenance는 유지하고 `not_attempted` 및 구체적 사유를 기록한다.

- figure/table 영역 OCR이 변환 단위 세션을 공유한다. 페이지별 렌더·결과 캐시는 제한된 수명으로 관리하고 페이지 처리 후 해제한다.
- 동일 page/crop/scale/lang/backend/settings에 한해서 결과를 재사용한다.
- Tesseract text/confidence 호출 통합은 이번 범위에서 제외한다.
- 실제 OCR 호출 수, 제외 수, 페이지 렌더 수, 캐시 적중 수를 보고한다.
- 검증: 제외 후보 154건의 OCR 호출 0회, Markdown 동일, 유지 후보 증거 동일, 동일 환경 front-matter 중앙값 50% 이상 단축 목표. runtime 누락·잘못된 bbox·페이지 실패도 검사한다.

구현 결과(2026-09-13, PR merge 전): 장식 후보 제외, 한 페이지 렌더와 128개 crop 결과 캐시, 그림·표의 페이지 단위 공동 처리, 실제 작업량 지표를 추가했다. 전체 540개 테스트 및 lint/schema 검사 통과. 같은 로컬 환경의 cold 1회/warm 5회 비교에서 front-matter 중앙값 29.127초 → 2.086초(92.8% 단축), backend 호출 159 → 5회, 수정 후 렌더 1회를 확인했다. 세 실제 입력의 Markdown/manifest 및 유지 대상 OCR evidence는 동일하다. 상세 근거와 기존 visual validator 오류는 `docs/Q153_REGION_OCR_IMPLEMENTATION.md`에 기록했다.

### Q154. 빈 표 억제 및 벡터 도식 보존

셀 내용과 경계를 함께 검사하여 전부 빈 표를 확정 단계에서 제외하고 진단을 남긴다. 표 제외만으로 도식으로 승격하지 않는다. 원문 캡션과 도형 증거가 있는 경우 기존 crop 로직을 활용한다.

- 확정된 실제 표와 겹치는 Figure 캡션은 crop에서 제외한다.
- crop 성공 시 도식 내부 조각난 텍스트를 일반 본문에서 제거하되 figure evidence로 보존한다. 실패·불확실 시 원문 유지와 warning을 우선한다.
- 최종 빈 HTML 표는 fallback 여부와 무관하게 integrity 오류로 처리한다.
- 검증: controller 페이지 3의 빈 표 4개 제거와 도식 3개 보존, 페이지 4 실제 표 3개 유지, SGL 표 유지.

### Q155. 중첩 표 구조 보존

내부 셀 모델은 row/column/span/bbox/raw text/children을 가진다. 단순 bbox 겹침이 아닌 경계와 포함 관계로 중첩을 판정한다.

- 부모 `<td>` 내부에 실제 HTML `<table>`을 직렬화하고 병합 셀은 HTML로 보존한다.
- `TableAsset.cell_structure` 및 선택적 row `cell_refs`를 추가한다. 기존 cells/row_text/최상위 table ID를 유지한다.
- 자식 ID는 부모 ID와 구조 위치에서 결정한다. 자식 표를 별도의 동일 검색 청크로 중복 생성하지 않는다.
- 확정 불가 시 원문 fallback과 actionable `structure_loss`를 기록한다.
- 검증: Figure 118/119 byte 15 안의 07:04/03:00 중첩 관계, 단순 표 불변, 순환·누락·중복 방지.

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

완료된 Q34-Q151 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
