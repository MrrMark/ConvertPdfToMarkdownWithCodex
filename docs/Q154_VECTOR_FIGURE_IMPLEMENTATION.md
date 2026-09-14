# Q154 빈 표 억제 및 벡터 도식 보존

2026-09-14 구현 및 로컬 검증 완료. PR merge 대기 상태다.

## 구현

- 표 후보 순위·중복 제거 전에 전부 빈 셀인 후보를 제외한다. 큰 빈 후보가 실제 표를 가리지 않도록 하고, 페이지·bbox와 advisory warning을 남긴다.
- 캡션, 닫힌 사각형 외곽, 내부 노드 2개 이상, 서로 다른 노드를 연결하는 선을 함께 확인하여 벡터 도식을 crop한다. 확정 표와 겹치거나 한 캡션이 여러 외곽에 대응하면 자동 보존을 하지 않는다.
- 각 crop을 자기 캡션 다음에 배치한다. crop에 완전히 포함된 조각난 텍스트만 본문에서 제외하고 원문 줄·좌표를 manifest와 figure sidecar의 `source_text_lines`에 보존한다.
- 렌더 실패·시간 초과·모호한 경계에서는 원문을 유지한다. Placeholder 모드에서도 본문 텍스트를 유지하며, sidecar 비활성화 시에도 manifest에 원문 evidence를 남긴다.
- 최종 빈 HTML 표를 artifact integrity error로 검출한다. 중첩 표와 이미지 셀을 구분하고 fenced code 예제는 제외한다.

주요 변경 파일은 `pdf2md/extractors/vector_figures.py`, `images.py`, `tables.py`,
`structure_normalizer.py`, `pdf2md/pipeline.py`, `models.py`, `serializers/manifest.py`,
`scripts/validate_artifact_integrity.py`다. Manifest schema와 출력 계약도 갱신했다.

## 실제 문서 검증

로컬 NVMe slice를 `technical_spec_rag_visual`, NVMe domain adapter로 변환했다.
원본 PDF와 실제 정답·산출물은 무시되는 `output/q154_validation/`에 보관한다.
저장소에는 원문이 없는 집계만 기록한다.

| 사례 | 결과 | 원문 품질 | 회귀 gate |
| --- | --- | --- | --- |
| Controller 5페이지 | 빈 표 4개 제거, 실제 표 3개 유지, 도식 729–731의 crop 3개 보존 | 통과 | 통과 |
| SGL 4페이지 | 표 10개 유지, Q153 대비 Markdown·manifest 바이트 동일 | 기존 중첩 표 실패 2건 | 통과 |
| Front matter 5페이지 | Q153 대비 Markdown·manifest 바이트 동일 | 통과 | 통과 |

Controller의 해결된 5개 검사에 대해서만 새 로컬 truth에서 알려진 실패 목록을 제거했다.
정답의 bbox·토큰·기대 표 개수와 기존 Q152 truth는 변경하지 않았다.
도식 crop 3개는 원본 페이지와 시각적으로 비교해 테두리·노드·라벨·연결선 보존을 확인했다.
세 사례 모두 artifact/index/provenance 검사를 통과했다.
Controller 실제 표의 셀·좌표·직렬화는 유지되었다. 앞 페이지의 빈 표가 사라짐에 따라
첫 실제 표에서 불필요해진 continuation 판정 진단만 제거되었다.

Visual 계약 검사는 기존 Q159 문제로 front matter 462건, controller 22건이 남아 있다.
Front matter finding 목록은 동일하다. Controller는 그림 3개 추가에 따라 뒤쪽 evidence의
줄 번호·순번 ID가 이동했으며, 나머지 finding 내용과 개수는 동일하다.
SGL visual 계약 검사는 통과했다. 내부 무결성 통과를 전체 원문 품질 통과로 해석하지 않는다.

## 회귀 검증

`tests/test_vector_figures.py`는 도식 보존·캡션 순서·실제 표 유지·빈 표 제외,
렌더 실패·시간 초과 시 텍스트 유지, 기하학적 근거 누락, 모호한 캡션,
placeholder 및 sidecar 비활성화, 실제 2페이지 병렬 처리 동등성,
최종 HTML 중첩 표·이미지 셀·fenced code 검사를 포함한다.
전체 unit/integration/CLI/golden 테스트 555개(Q154 15개 포함)가 통과했다.
Ruff, schema 동기화 검사, CLI help도 통과했다.
Golden 기준 파일은 변경하지 않았다. 최종 집계는 `evaluation/q154_validation_2026-09-14.json`을 참조한다.

## 제한사항과 다음 작업

- 현재 자동 검출 범위는 위쪽 40pt 이내 캡션이 있는 사각 외곽·사각 노드·직선 연결 도식이다. 외곽 없는 도식, 곡선 연결, 아래쪽 캡션은 이번 자동 검출 범위에 포함하지 않는다.
- 텍스트가 있는 표 후보는 보수적으로 유지하므로 일부 도식이 표로 오인된 경우에도 자동 복구가 제한될 수 있다.
- 시간 제한은 crop 사이에서 확인한다. 단일 렌더 호출을 중간에 강제 종료하지 않는다.
- 이번 검증은 로컬 CPU 결과이며 Windows CI와 독립 성능 비교는 실행하지 않았다. 속도 개선 수치를 주장하지 않는다.
- 다음 개발은 Q155의 중첩 표 구조 보존이다. 기존 visual 참조 계약 문제는 Q159에서 처리한다.
