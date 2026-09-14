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


### Q156. 비교 벤치마크 공정성

동일 slice를 독립 프로세스에서 처리한다. native 유효 CLI 옵션을 기록하고 Docling의 실제 document 객체에서 표·그림 수를 센다.

- input hash, 패키지/모델 버전, worker/thread, peak RSS를 기록한다.
- import·설정·모델 다운로드와 convert+export/write를 분리한다.
- cold 1회와 warm 5회의 중앙값 및 범위를 사용한다. 소표본 p95는 보고하지 않는다.
- 원문 품질, 처리량, 기능 지원을 분리하며 미지원 기능을 품질 0점으로 환산하지 않는다.

2026-09-14 구현·로컬 검증 완료. 새 성능 계측 진입점은 `scripts/benchmark_fair_comparison.py`다.
전체 575개 테스트 통과. [Q156 구현 결과](Q156_FAIR_BENCHMARK_IMPLEMENTATION.md)에
공통 slice·독립 프로세스·계측 범위·버전/메모리 계약과 실제 native smoke 결과를 기록했다.
Docling 실제 변환은 모델 준비 후 Q157에서 수행한다. PR merge까지 이 항목을 유지한다.

### Q157. 외부 CPU 도구 비교 실험

별도 환경에 Docling 2.126, Marker 2.0 fast, PyMuPDF4LLM 1.27.2.2를 고정하여 Q152 corpus를 비교한다. 각 버전 설치 가능 여부부터 확인하고 정확한 패치 버전을 실행 기록에 남긴다.

- 원본은 로컬에서만 파싱하고 모델 다운로드는 계측에서 제외한다.
- 설치·실행 불가 시 사유를 기록한다. 임의 버전 변경 또는 클라우드 대체 실행은 하지 않는다.
- MinerU/Paddle VLM/GPU는 필수 비교에서 제외한다. 결과는 향후 채택 판단용이며 제품 backend 통합은 별도 작업이다.

2026-09-14 구현·로컬 검증 완료, PR merge 대기.
Native·Docling 2.126.0·PyMuPDF4LLM 1.27.2.2를 3개 corpus에서 각 6회 실행했고,
Marker 2.0.0은 로컬 llama-server 부재를 명시했다. 전체 테스트 582개 통과.
상세 결과·재현·한계는 [Q157 실험 보고서](Q157_EXTERNAL_CPU_EXPERIMENT.md)에 기록했다.

### Q158. 한글 검색 평가 및 회귀 마감

기존 lexical smoke를 유지하고 Unicode 단어·기술 식별자·한글 문자 bigram 기반 로컬 BM25 기준선을 추가한다.

- 사람이 검토한 한글 15개·영어 15개 질문에 requirement/table/figure 원문 참조를 부여한다.
- Recall@5, MRR@5, citation 및 중요 토큰 보존을 평가한다. embedding/reranker/LLM 평가는 범위 밖이다.
- 로컬 Mac, Windows CPU CI, 기존 Linux CI를 검증한다.
- 전체 회귀와 release gate를 실행하고 원문 품질과 내부 무결성 결과를 각각 보고한다.

2026-09-14 BM25 및 별도 한·영 평가 CLI 구현. 질문 30개는 로컬 검토 초안이며 사람 검토 대기다.
2026-09-15 원문 렌더링 대조와 중요 토큰 검사 보완 완료. Mac Python 3.11/3.14 각 592개,
PR #142의 Windows Python 3.11 및 Linux Python 3.11/3.14 CI가 모두 통과했다.
사람 검토 승인과 PR merge는 대기 중이다.
진행 결과와 잠정 지표는 [Q158 보고서](Q158_BILINGUAL_RETRIEVAL_EVALUATION.md)에 기록한다.

### Q159. Visual sidecar 참조 계약 검증

Q153 실측 중 이전 버전부터 존재하던 visual 계약 오류를 발견했다. front matter 462건, controller 22건이며 수정 전후 finding 목록은 동일하다.

- 실제 source reference의 `figure`/`excluded_figure` 타입과 ID를 확인하고 생산자·검증기 중 어느 계약이 잘못됐는지 재현 fixture로 구분한다.
- description/OCR evidence/structure의 정당한 참조를 수용하되 실제 누락·잘못된 target ID 검출은 유지한다.
- 실제 레코드 삭제나 검사 생략으로 오류를 숨기지 않는다.
- 합성 정상/실패 회귀 검사와 기존 실제 두 사례의 오류 해소를 완료 기준으로 삼는다. Q153에서는 수정하지 않는다.

## 완료 명세 Archive

완료된 Q34-Q155 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
