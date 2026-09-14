# Q155 중첩 표 구조 보존

2026-09-14 구현 및 로컬 검증 완료. Q154 변경을 유지한 상태에서 구현했다. PR merge 전까지 active 명세에 유지한다.

## 구현 내용

- 선 기반 PDF 표 후보와 실제 셀 경계를 사용한다. 자식 bbox가 부모 표 안에 있다는 사실에 더하여 정확히 하나의 부모 셀에 포함되는지 검사한다.
- 행·열·병합 범위·bbox·원문·자식 표를 갖는 `TableCellStructure`와 `NestedTableStructure`를 추가했다. 자식 텍스트를 평문으로 반복하지 않고 부모 `<td>` 안의 `<table>`로 직렬화한다. Rowspan·colspan도 HTML에 반영한다.
- 확인된 부모 표를 자식 후보보다 먼저 확정하여 품질 점수가 높은 자식도 별도의 최상위 검색 레코드로 중복 생성되지 않게 한다.
- 기존 RAG `cells`와 `row_text`는 그대로 유지한다. `cell_refs`만 추가하여 manifest의 셀 구조에 연결한다. ID는 부모 위치에서 결정하며 순차·병렬 실행에서 동일하다.
- 셀 누락·중복·겹침·부모 경계 침범·깊이 초과·텍스트 순서가 모호하면 기존 평문으로 남기고 `TABLE_STRUCTURE_LOSS`를 보고한다. 원문을 삭제하거나 추측한 연결을 출력하지 않는다.
- Artifact 검사에 구조 ID 유일성과 셀 참조 해소 검사를 추가했다. Q152 원문 평가의 `table_cell` 검사는 해당 셀의 자식 내용을 포함하도록 확장했다. `nested_table` 검사는 실제 HTML 소유 관계를 계속 요구한다.

주요 파일은 `pdf2md/extractors/nested_tables.py`, `tables.py`, `pdf2md/models.py`,
`serializers/manifest.py`, `pdf2md/quality_eval.py`, `scripts/validate_artifact_integrity.py`다.
출력 계약은 `OUTPUT_SCHEMA.md`와 `schema/manifest.schema.json`에 반영했다.

## 검증 범위

합성 fixture에서 실제 중첩 HTML과 원문 토큰, 상위 검색 행 수, 셀 참조, 강제 Markdown 요청의 안전한 HTML 전환,
rowspan·colspan, 잘못된 부모 연결·중복·누락, 낮은 점수의 부모 보존, 구조 손실 경고,
반복 실행·2페이지 병렬 실행의 동일 ID를 검사한다. 일반 표 golden은 변경하지 않는다.

전체 unit/integration/CLI/golden 테스트 **566개**가 통과했다. Q155 전용 테스트는 11개이며
기존 Q152 원문 회귀도 알려진 실패 없이 통과하도록 강화했다. Ruff·schema 동기화·CLI help 검사도 통과했다.
집계는 [검증 JSON](evaluation/q155_validation_2026-09-14.json)에 기록한다.

실제 SGL 4페이지의 Figure 118·119에서는 byte 15의 Description 셀 안에
07:04·03:00 비트 표가 들어가는 원본 구조를 확인했다.
Q152 truth의 기대 셀·토큰·부모 관계는 유지하고, 새 로컬 truth에서 해결된 중첩 표 실패 예외만 제거했다.
기존 truth를 덮어쓰거나 출력에서 정답을 역생성하지 않았다.

| 사례 | 최상위 표 / 검색 행 | 중첩 구조 | 원문 gate / 내부 무결성 |
| --- | --- | --- | --- |
| SGL 4페이지 | 10 / 43, 기존 행 원문 동일 | 부모 표 7개에서 보존 | 원문 quality·gate 및 artifact/index/provenance/visual 모두 통과 |
| Controller 5페이지 | 3 / 7, 기존 행 원문 동일 | 없음 | 원문 quality·gate 및 artifact/index/provenance 통과 |
| Front matter 5페이지 | 0 / 0 | 없음 | 원문 quality·gate 및 artifact/index/provenance 통과 |

Controller와 front matter는 Q154 대비 `document.md`·`manifest.json` 바이트가 동일하다.
기존 visual 오류 22건·462건도 finding 목록까지 동일하며 Q159에서 처리한다.
SGL의 원문 검사는 지정된 정답 항목에 대한 통과이며 문서 전체의 모든 셀을 사람이 검수했다는 의미는 아니다.
PDF 내 작은 독립 공백을 후행 본문으로 오인하지 않도록 보완하고 합성 fixture에도 재현했다.

원본 PDF 렌더를 시각적으로 확인하고, 생성 HTML의 부모 셀 관계와 텍스트를 검사했다.
브라우저 보안 정책이 로컬 HTML 미리보기 URL을 차단하여 생성 HTML의 화면 검증은 수행하지 못했다.
실제 원문·truth·결과는 무시되는 `output/q155_validation/`에 보관하고 집계만 저장소에 남긴다.

## 제한사항과 다음 단계

- 선 기반 경계와 기존 셀 텍스트 사이의 대응이 명확한 경우에 한정한다. 텍스트 정렬만으로 추정한 가상 표는 중첩 근거로 사용하지 않는다.
- 자식 앞에 있는 부모 설명은 지원한다. 자식 사이·아래에 부모 텍스트가 섞여 재배치될 위험이 있으면 구조 손실 진단과 평문 보존을 선택한다.
- 중첩 깊이는 8단계까지 허용하며, 면적이 엄격하게 감소하도록 하여 순환을 방지한다.
- 자식별 독립 검색 청크는 만들지 않는다. 필요하면 상위 행의 `cell_refs`와 manifest 구조를 활용한다.
- 기존 Q159 visual 참조 계약 문제는 별도 과제로 유지한다. Windows CI와 외부 도구 성능 비교는 이번 로컬 검증 범위에 포함하지 않는다.
- 다음 권장 개발은 Q156 비교 벤치마크 공정성이다.
