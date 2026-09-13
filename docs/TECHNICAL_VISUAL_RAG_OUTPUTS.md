# Technical Visual RAG 산출물 안내

`technical_spec_rag_visual`은 기술 사양 PDF를 Markdown과 RAG용 sidecar 파일로 변환하는 프로필입니다. 아래 설명은 전체 sidecar 출력과 기본 이미지 모드(`referenced`)를 기준으로 합니다.

실행 예시는 다음과 같습니다.

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag_visual \
  --domain-adapter nvme
```

JSONL 파일은 한 줄마다 독립된 JSON 레코드 하나를 저장합니다. 원문 인용과 근거 추적에는 각 레코드의 `source_refs`, 페이지, 좌표(`bbox`), 입력 PDF 해시를 사용합니다.

## 기본 산출물

| 파일 또는 경로 | 용도 |
| --- | --- |
| `document.md` | 사람이 읽는 최종 Markdown 문서입니다. 추출 본문, 표, 이미지 상대 경로 참조와 선택 시 페이지 표식을 포함합니다. |
| `assets/images/page-0001-figure-001.*` | PDF에서 추출한 실제 이미지 asset입니다. 파일명은 페이지 번호와 페이지 내 그림 순번으로 결정됩니다. |
| `manifest.json` | 입력 문서, 적용 옵션, 생성 asset 및 sidecar에 대한 메타데이터입니다. 재처리와 산출물 연결 확인에 사용합니다. |
| `report.json` | 변환 상태, 경고, 부분 실패 페이지, 레코드 수, 품질 진단을 기록합니다. 변환 결과 검수의 기준 파일입니다. |
| `conversion_state.json` | 변환 중 및 완료 후의 현재 단계, 완료·실패 페이지, 작성된 artifact 목록을 기록합니다. 중단 후 재실행·원인 분석에 사용합니다. |

## RAG 검색과 원문 근거

| 파일명 | 용도 |
| --- | --- |
| `retrieval_chunks_rag.jsonl` | RAG 인덱싱의 주 입력입니다. 텍스트, 표, 요구사항, 그림 관련 정보를 검색 단위로 구성하며, 원문 근거와 문맥·청크 관계를 보존합니다. 임베딩 벡터를 저장하는 파일은 아닙니다. |
| `text_blocks_rag.jsonl` | 제목, 문단, 목록, 코드, 각주, 캡션의 원문 블록과 페이지·좌표·제목 경로를 기록합니다. 검색 결과 원문 확인에 사용합니다. |
| `semantic_units_rag.jsonl` | 원문 블록을 절, 요구사항, 정의, 파라미터, 절차, 주의사항, 참조 등으로 보수적으로 분류합니다. 유형별 검색과 필터링에 사용합니다. |
| `requirements_rag.jsonl` | `semantic_units_rag.jsonl` 중 요구사항으로 분류된 레코드입니다. 규범 강도와 안정적인 원본 식별자를 제공합니다. |
| `requirement_traceability_rag.jsonl` | 요구사항 ID, 조건, 적용 범위, 예외, 의존 참조, 표 행 연결 및 검증 의도를 기록합니다. 요구사항 추적과 검증 계획 수립에 사용합니다. |
| `cross_refs_rag.jsonl` | 절·표·그림·부록 등 문서 내부 참조와 대상 연결 결과를 기록합니다. 해석하지 못한 참조의 사유도 포함합니다. |

## 표와 도메인 구조화

| 파일명 | 용도 |
| --- | --- |
| `tables_rag.jsonl` | 표의 행·셀·헤더 계보·원본 위치를 저장합니다. 표 내용 검색과 행 단위 근거 추적에 사용합니다. |
| `rag_tables.md` | 추출 표를 별도 Markdown으로 직렬화한 파일입니다. 표 중심 검토나 Markdown 기반 RAG 입력에 사용합니다. |
| `technical_tables_rag.jsonl` | 기술 표 행을 opcode, 레지스터, 비트필드, 상태 코드, 명령 필드 등으로 구조화합니다. 기술 사양의 정밀 검색과 필드 분석에 사용합니다. |
| `domain_units_rag.jsonl` | 선택한 도메인 어댑터(NVMe, PCIe, OCP, TCG, SPDM, Caliptra 등)가 식별한 도메인 단위입니다. `--domain-adapter`를 지정한 경우에만 생성합니다. |

## 페이지와 그림 분석

| 파일명 | 용도 |
| --- | --- |
| `page_layout_rag.jsonl` | 페이지별 읽기 순서, 다단 여부, 텍스트·표·그림 영역, 캡션 연결을 기록합니다. 레이아웃 기반 품질 진단과 provenance에 사용합니다. |
| `figures_rag.jsonl` | 그림 ID, 경로, 페이지·좌표, 캡션, 감지 라벨, 인접 텍스트 참조를 기록합니다. 그림 검색과 이미지 asset 연결의 기준 파일입니다. |
| `figure_ocr_evidence_rag.jsonl` | 그림·표 영역 OCR의 텍스트, 신뢰도, 채택 또는 거절 사유를 기록합니다. OCR 증거 검토용이며 `document.md` 원문을 바꾸지 않습니다. |
| `figure_descriptions_rag.jsonl` | 캡션, 라벨, 주변 텍스트, OCR 증거로 구성한 그림 검색 보조 설명입니다. 생성 텍스트 여부와 검토 필요 여부를 함께 기록합니다. |
| `figure_structures_rag.jsonl` | 다이어그램의 관측 라벨, 노드, 신호, 관계 단서를 저장합니다. 구조 검색과 사람 검토를 위한 보조 자료입니다. |

그림 설명과 구조 정보는 Markdown 본문에 삽입하지 않습니다. 현재 구현은 캡션·라벨·주변 텍스트·OCR 등 관측 가능한 근거를 사용하며, 이미지 픽셀을 해석한 사실로 표현하지 않습니다. 따라서 원본 그림을 대체하는 자료가 아니라 검색과 검토를 돕는 sidecar입니다.

## 조건부 산출물과 생성 조건

| 파일 또는 경로 | 생성 조건 및 용도 |
| --- | --- |
| `interrupted_report.json` | `KeyboardInterrupt` 또는 치명적 예외로 변환이 중단되면 생성합니다. 중단 시점, 실패 원인, 남은 산출물, 재개 안내를 기록합니다. |
| `sanitized_report.json` | `--confidential-safe-mode`에서 생성하는 공유용 정제 보고서입니다. 민감한 경로·입력 식별 정보 노출을 줄입니다. |
| `debug/page-0001-raw-lines.json` | `--debug`에서 생성합니다. 페이지의 원시 텍스트 추출 행과 메타데이터입니다. |
| `debug/page-0001-ordered-lines.json` | `--debug`에서 생성합니다. 읽기 순서를 적용한 텍스트 행입니다. |
| `debug/page-0001-normalized-lines.json` | `--debug`에서 생성합니다. 안전한 정규화 후 텍스트 행입니다. |
| `debug/page-0001-table-candidates.json` | `--debug`에서 생성합니다. 표 검출 후보와 진단 정보입니다. |
| `debug/page-0001-image-candidates.json` | `--debug`에서 생성합니다. 그림 검출 후보와 진단 정보입니다. |
| `debug/table-quality-review-pack.json` | 표 품질 검토 데이터가 준비된 경우 생성하는 진단 자료입니다. |

`image_mode=placeholder`를 사용하면 실제 `assets/images/` 파일을 쓰지 않고 Markdown에 placeholder를 남기며, 그림 RAG sidecar는 가능한 범위에서 유지합니다. `image_mode=none`을 사용하면 이미지 추출과 그림 sidecar 기능이 생략될 수 있습니다. 그림·표·요구사항 등 해당 데이터가 없는 문서에서는 관련 JSONL 파일이 비어 있거나 생성되지 않을 수 있습니다.

정확한 필드 계약은 [OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md)를, 프로필 옵션은 [rag_profiles.py](../pdf2md/rag_profiles.py)를 참조하십시오.
