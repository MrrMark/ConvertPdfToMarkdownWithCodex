# Q153 선택적 영역 OCR 및 렌더 재사용

2026-09-13 구현·로컬 검증 완료. 기존 visual RAG 프로파일과 `--figure-region-ocr` 경로에 기본 적용한다.

## 구현 내용

- 이미 제외된 `TINY_DECORATIVE` 후보만 영역 OCR에서 생략한다. 실제 이미지 및 다른 제외 사유에는 적용하지 않는다.
- 제외된 그림 레코드와 provenance를 유지한다. 그림 진단은 `not_attempted/tiny_decorative/attempted=false`, OCR evidence는 `not_attempted/rejected_reason=tiny_decorative`로 기록한다.
- 그림과 OCR 대상 표를 페이지 순서로 함께 처리한다. 준비한 결과는 기존 그림 순서와 table ID에 맞춰 소비하므로 evidence ID와 파일명은 유지된다.
- `RegionOCRCache`는 한 페이지의 PDFium bitmap/PIL 이미지와 최대 128개의 crop 결과만 유지한다. 페이지 경계 및 종료·실패 경로에서 이미지, bitmap, page를 닫고 결과 캐시를 비운다. PDF 문서도 처리 종료 시 닫는다.
- 동일 페이지의 같은 픽셀 crop, backend 인스턴스, OCR 언어, 렌더 scale에서 결과를 재사용한다. 입력 bbox가 조금 달라도 같은 픽셀 crop이면 OCR 결과만 재사용하고 각 후보의 원래 bbox는 유지한다.
- 캐시는 변환 단위로 한정한다. backend 설정은 해당 변환의 runtime 초기화 때 고정되며, 다른 입력·변환·언어·backend의 결과를 혼용하지 않는다.
- Tesseract의 text/confidence 호출 방식, 원문 텍스트, 표 직렬화, 이미지 추출은 변경하지 않았다.

구현 파일은 `pdf2md/serializers/rag_figure_semantics.py`, `pdf2md/serializers/rag_ocr_evidence.py`, `pdf2md/pipeline.py`다.
새 지표의 JSON Schema는 `pdf2md/models.py`와 `docs/schema/report.schema.json`에 반영했다.

## 보고 지표와 계측 구간

`report.json.summary`에 실제 backend 호출, 페이지 렌더, 페이지/결과 cache hit, 장식 후보 제외 수를 추가했다.
정확한 필드와 기존 counter의 의미는 [출력 계약](OUTPUT_SCHEMA.md)을 따른다.

그림과 표의 공유 OCR 준비는 `rag_figures` 단계에서 수행한다. 이후 `rag_ocr_evidence` 단계는 준비된 표 결과를 이용한다.
따라서 이전 버전과 단계별 시간만 직접 비교하지 않고 **전체 변환+산출물 저장 시간**과 새 작업량 counter를 비교해야 한다.
재사용 경로가 없는 별도 serializer 호출도 페이지 캐시를 사용하지만, 그림·표 간 공유는 pipeline의 통합 준비 경로에서 보장한다.

## 같은 환경에서 측정한 결과

Mac arm64 / Python 3.11 로컬 CPU에서 동일 PDF와 `technical_spec_rag_visual`, domain `nvme`, page worker 1 설정으로 비교했다.
현재 작업과 분리된 디렉터리에 기존 runtime 파일을 Git HEAD에서 복원했다. 이전 버전 실행이 끝난 뒤 수정 버전을 별도 프로세스에서 실행했다.
front matter는 각 버전 cold 1회 + warm 5회이며, import를 제외하고 변환과 산출물 저장을 포함했다. backend 호출 수는 wrapper로 직접 계측했다.
하드웨어 격리는 하지 않았으며 외부 도구와의 비교 결과가 아니다.

| front matter 5페이지 | 수정 전 | 수정 후 |
| --- | ---: | ---: |
| warm 5회 중앙값 | 29.127초 | 2.086초 |
| warm 범위 | 27.007–34.580초 | 2.054–2.193초 |
| 실제 OCR backend 호출 | 159회 | 5회 |
| 명시적 장식 후보 OCR 제외 | 0건 | 154건 |
| 수정 후 실제 페이지 렌더 | — | 1회 |
| 수정 후 페이지 이미지 재사용 | — | 4회 |

중앙값은 **92.8% 단축**되어 Q153의 50% 목표를 충족했다. 실제 OCR 대상 5개가 같은 페이지에 있어 렌더 1회로 처리됐다.
이 사례에는 같은 crop의 반복 요청이 없으므로 result cache hit는 0이다. 그림·표의 동일 crop 공유는 합성 테스트에서 backend 호출 수로 검증했다.

controller/SGL slice는 각각 1회씩 추가 실행하여 호환성을 확인했다. 이 단발 실행의 시간 차이는 성능 개선율로 일반화하지 않는다.
controller의 기존 장식 후보 7개도 제외되어 실제 backend 호출이 8회에서 1회로 줄었다. SGL은 1회를 유지했다.

측정 원시 수치·버전·입력 hash는 [공유 가능한 집계 JSON](evaluation/q153_region_ocr_validation_2026-09-13.json)에 보관한다.
원본 PDF·전체 산출물·측정 스크립트는 Git 제외 경로 `output/q153_validation/`에 보관한다.

## 호환성 및 회귀 검증

- NVMe 3개 입력 모두 이전 버전과 `document.md`, `manifest.json`이 byte 단위로 동일했다. front matter의 모든 반복에서도 동일한 Markdown hash를 유지했다.
- 유지 대상 OCR evidence는 front matter 5건, controller 1건, SGL 1건 모두 이전 버전과 동일했다. 제외 후보도 evidence 레코드 자체는 유지했다.
- Q152의 front-matter 정답에서 해결된 3개 OCR 허용 목록만 제거한 새 로컬 정답으로 `quality_passed=true`, `gate_passed=true`를 확인했다. Q152 당시의 정답과 보고서는 보존했다.
- controller/SGL의 빈 표·도식·중첩 구조 실패는 기존과 동일하게 재현되어 기준선 gate를 통과했다. 이 문제들은 Q154/Q155에서 수정한다.
- 전체 **540개 테스트**, Ruff, JSON Schema 검사 통과. 기존 golden은 갱신하지 않았다.
- 실제 세 출력의 artifact/index/provenance 검사 통과.

신규 테스트는 장식 후보만 제외되는지, 다른 제외 사유 유지, runtime 미설치, 잘못된 bbox, 페이지/인식 실패 후 계속 처리,
페이지·언어·backend·세션별 캐시 분리, 128개 캐시 제한, bbox provenance, 그림·표 공유 및 evidence 정렬/ID를 검사한다.

## 남은 항목

별도 visual sidecar 계약 검사는 기존 출력에도 front matter 462건, controller 22건의 참조 오류가 있다.
수정 전후 오류 목록이 완전히 같으며, 주로 제외된 그림의 source reference 검사에서 발생한다. 이 결과를 통과로 표시하지 않았다.
새 Q159에서 validator와 생산자의 참조 계약을 함께 확인한다. SGL의 visual 검사는 통과했다.

Windows CPU 실측과 CI 확장은 Q158에서 진행한다. Q153에는 외부 backend 도입이나 GPU 의존성을 추가하지 않았다.
