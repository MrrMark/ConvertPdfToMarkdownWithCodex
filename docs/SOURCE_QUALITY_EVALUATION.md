# 원문 기준 품질 평가 (Q152)

`scripts/evaluate_source_quality.py`는 **직접 작성한 원문 정답과 변환 결과를 비교**한다. 기존 artifact/index/provenance 무결성 검사를 대체하지 않는다. 전체 문서 정확도 점수를 추정하지 않으며 정답에 명시한 항목의 통과 여부만 보고한다.

## 실행

```bash
python scripts/evaluate_source_quality.py \
  --input-pdf output/docling_nvme_base_slices/controller_tables_p696_700.pdf \
  --output-dir output/tool_review_20260911/controller_tables/pdf2md/run-0 \
  --truth output/source_quality_q152/controller_tables.truth.json \
  --report output/source_quality_q152/controller_tables.report.json
```

- 정답과 PDF의 SHA-256이 달라지면 실행을 거부한다. slice의 모든 페이지를 원본 물리 페이지에 연결해야 한다.
- 보고서는 입력 PDF, 정답 파일, 변환 출력 디렉터리와 분리한다. 평가기는 변환 산출물을 수정하지 않는다.
- 종료 코드 `0`: 기준선 유지, `1`: 새 실패 또는 오래된 허용 목록, `2`: 입력/정답/실행 오류.
- `gate_passed=true`여도 `quality_passed=false`일 수 있다. 알려진 실패가 정확하게 재현됐다는 뜻이다.
- `quality_passed=true`는 등록한 검사에 한정한다. 정답이 없는 나머지 페이지·내용의 정확성을 보증하지 않는다.
- 반복 실행 결과에는 시간·절대 경로가 들어가지 않으며 같은 입력/정답/출력에서 결정적인 JSON을 생성한다.

## 정답 작성

실제 문서는 원본을 렌더해서 확인한 뒤 사람이 정답을 작성한다. 변환 Markdown이나 sidecar를 정답으로 복사하지 않는다. 관측된 실패의 식별자는 `known_failure_records`에 별도로 기록할 수 있다. 실제 원문·정답·페이지 렌더는 Git에서 제외된 `output/`에만 보관한다.

공유용 저장소에는 합성 검사 코드, 원본 식별 정보, 집계 결과만 둔다. 보고서에는 원문 정답 토큰이 포함되지 않는다. 세부 보고서는 record ID를 포함하므로 외부 공유 전 검토한다.

```json
{
  "schema_version": "1.0",
  "case_id": "synthetic-table",
  "input_sha256": "<실제 PDF의 SHA-256 64자리>",
  "reviewed_from": "synthetic_source_definition",
  "review_note": "fixture 정의를 기준으로 작성",
  "pages": [{"page": 1, "physical_page": 25, "printed_page": "1"}],
  "checks": [{
    "check_id": "nested-bits",
    "kind": "nested_table",
    "page": 1,
    "record_id": "page-0001-table-0001",
    "row_label": "15",
    "column": 1,
    "tokens": ["Bits", "07:04", "03:00"],
    "known_failure_records": ["page-0001-table-0001"]
  }]
}
```

`reviewed_from`은 실제 PDF이면 `rendered_source_pdf`, 합성 정의이면 `synthetic_source_definition`을 사용한다. 중복 check ID, 중복 페이지, 없는 페이지 참조, 잘못된 bbox, 필수 조건 누락은 오류다.

| kind | 확인 대상 | 필요한 추가 필드 |
| --- | --- | --- |
| `text_sequence` | 지정 페이지에서 원문 토큰이 지정 순서로 나타나는지 | `tokens` |
| `table_count` | Markdown에 직렬화된 최상위 HTML/GFM 표 개수 | `count` |
| `table_cell` | 표의 행·셀 안에 원문 토큰 보존 | `record_id`, `row_label`, `column`, `tokens` |
| `nested_table` | 지정한 부모 셀 내부의 실제 HTML 자식 표 | 위와 동일 |
| `figure_region` | 원문 캡션, bbox IoU, 사용 가능한 실제 이미지 파일 | `record_id`, `tokens`, `bbox`, 선택적 `minimum_iou` |
| `no_empty_tables` | 텍스트·이미지 참조·내용 있는 자식 표가 모두 없는 최상위 HTML/GFM 표 | 없음 |
| `no_decorative_ocr` | TINY_DECORATIVE 후보 수 및 명시적 OCR 제외 증거 | `count` |

`row_label`은 행의 첫 번째 셀과 일치해야 한다. `column`은 직렬화된 셀의 0 기준 위치다. rowspan/colspan의 논리 좌표 확장은 현재 하지 않는다. 중첩 판정은 문자열 포함이 아니라 HTML 트리의 부모 셀 안 자식 `<table>`에 적용한다. 일반 표는 표 주석이 붙은 기존 native GFM 출력을 지원한다.

토큰 검사는 NFC·공백 정리와 출력 entity 해제 외에는 대소문자·기호를 바꾸지 않는다. 이 검사는 CER/WER 전체 텍스트 정렬이나 OCR 정답률을 계산하지 않는다. 도식 검사도 픽셀 의미 동등성을 자동 판정하지 않으므로 crop 내용은 원본 렌더와 별도로 확인해야 한다.

## 알려진 실패 관리

`known_failure_records`는 **정확한 실패 record ID 집합**이다. 범위·와일드카드·전체 페이지 예외는 허용하지 않는다. `table_count`처럼 수치 자체가 실패인 검사는 `page-0003:count=4`로 관측 수를 포함한다.

- 실패 집합이 정확하게 같으면 `known_failure`.
- 허용되지 않은 실패 또는 일부만 일치하면 `regression`.
- 모두 해결됐는데 허용 목록이 남으면 `stale_allowlist`.
- 실패도 허용 목록도 없으면 `passed`.

수정 후 결과를 확인하고 해당 실패만 허용 목록에서 제거한다. 자동으로 허용 목록이나 정답을 업데이트하는 기능은 제공하지 않는다.

## 초기 결과와 범위

2026-09-13 평가: 2026-09-11에 생성한 native visual profile 출력 3종·14페이지에서 17개 assertion을 검사했다.

| 대상 | 검출된 문제 | 정상 확인 항목 |
| --- | --- | --- |
| front matter 5페이지 | 장식 후보 154개가 영역 OCR 대상에 포함됨 | 목차 핵심 텍스트 순서 |
| controller 5페이지 | 빈 표 4개, 도식 3개가 이미지로 보존되지 않음 | 실제 표 3개, TCP/RoCE/iWARP 프로토콜 값 |
| SGL 4페이지 | Figure 118/119 중첩 구조 2개 손실 | byte 범위 행, 중요 길이 상수, 최상위 표 2개 |

세 사례 모두 `gate_passed=true`, `quality_passed=false`다. 이 결과는 이전 변환 실행을 평가한 것이며 새로운 속도 측정 결과가 아니다.

합성 단위 검사는 빈 표·평탄화된 중첩 표·잘못된 부모 셀·한영 토큰·읽기 순서·도식 위치·이미지 파일 누락·OCR 제외 증거·허용 목록 회귀·잘못된 입력을 검사한다. 정상 단순 표와 부모 셀 내부의 중첩 표는 합성 PDF의 실제 변환 통합 검사로 검증한다. 중첩 표의 평탄화는 명시적 알려진 실패이며 Q155에서 수정 후 허용 목록을 제거해야 한다. 기존 golden corpus의 OCR/한글/멀티컬럼/병합 표 검사도 함께 실행한다. 실제 corpus 정답은 로컬 전용이므로 기본 CI에서는 합성 검사만 실행한다.

현재 평가기는 native 출력 구조를 대상으로 한다. 외부 도구의 출력 어댑터와 새로 생성한 출력의 실행 메타데이터 연결은 Q156/Q157에서 진행한다. 캐시/선택 OCR(Q153), 도식/빈 표(Q154), 중첩 셀 구현(Q155)은 이 평가 기준선을 사용한다.
