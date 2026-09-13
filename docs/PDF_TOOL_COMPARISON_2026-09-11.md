# PDF 변환 도구 비교 및 개선 검토 — 2026-09-11

## 결론

이 프로젝트는 기술 사양의 요구사항·도메인 필드·원본 참조를 연결하는 계층을 유지할 가치가 있다. 그러나 현재의 Visual RAG 추출 품질과 내부 평가만으로 범용 파서보다 우수하다고 판단할 수는 없다. 이번 실측에서는 불필요한 영역 OCR, 도식을 빈 표로 오인하는 문제, 중첩 표의 내부 구조 손실을 확인했다.

권장 방향은 **현재 산출물 계약과 도메인 분석 계층을 유지하면서, 객관적인 평가를 먼저 보강하고 어려운 영역에만 검증된 추출기를 선택적으로 사용하는 것**이다. 전체 엔진 교체보다 OCR 대상 선별·렌더 재사용·표/그림 구분을 먼저 개선하는 편이 현재 근거에 부합한다.

이 문서는 조사와 실험 결과 및 후속 제안이다. 운영 코드·의존성·기존 개발 계획은 변경하지 않았으며, 아래 제안을 확정된 개발 일정으로 간주하지 않는다.

## 조사 범위와 근거 수준

- 로컬 마지막 커밋: `13caebb`, 2026-06-22. 조사일까지 81일이다.
- 외부 조사: GitHub 공식 README, 릴리스, PR, 벤치마크 저장소와 논문을 확인했다. 접근일은 2026-09-11이다.
- 직접 실측: 현재 `pdf2md`와 설치된 **Docling 2.103.0**. 외부 모델을 새로 다운로드하거나 PDF를 원격 서비스로 보내지 않았다.
- 공개 자료 비교: 최신 Docling, Marker 2, MinerU, PaddleOCR, PyMuPDF4LLM, olmOCR, Xberg, MarkItDown. 이들 전체를 로컬에서 실행한 것은 아니다.
- 일반화 한계: 직접 실측은 동일한 NVMe Base 문서의 세 구간, 총 14페이지다. 한국어·스캔·수식·다른 도메인 전체의 정확도를 대표하지 않는다.

## 최근 변화와 비교 대상

| 도구 | 확인한 변화·특징 | 이 프로젝트에 대한 활용 판단 |
| --- | --- | --- |
| Docling | 2026-09-04의 2.126.0에 `NativePdfPipeline` 추가. 모델 없는 텍스트·비트맵 추출과 부분 실패 처리를 제공하지만, 이 경로는 표·제목·읽기 순서를 복원하지 않는다. | 표준 파이프라인의 레이아웃/표 인식은 품질 비교 대상으로, native 경로는 저수준 추출 속도 비교 대상으로 분리한다. |
| Marker 2 | 2026-07-20의 2.0.0에서 CPU용 경량 레이아웃과 텍스트 추출, 필요한 영역만 OCR하는 `fast` 모드, 공유 추론 서버 기반 처리 도입. | 영역별 OCR 선별, 텍스트 계층과 모델의 역할 분담, 작업자별 모델 중복 적재 방지를 참고한다. |
| MinerU | README에서 3.4의 PP-OCRv6 적용과 pipeline/hybrid/VLM 경로를 확인. 3.3의 `effort=medium/high`와 3.4는 각각 6월 11일·18일 변경으로, 개발 중단 이후의 새 기능으로 분류하면 안 된다. | 복잡 표·수식·그림 분석의 비교 후보. 도구 버전, backend, 모델 버전을 따로 기록해야 한다. |
| PaddleOCR | 7월 22일 HPD-Parsing 공개. PP-OCRv6 및 PaddleOCR-VL-1.6도 비교 가치가 있으나 각각 6월·5월 출시로 기존에 존재하던 기능이다. | 작은 OCR 모델 또는 문서 VLM을 선택적 재처리 후보로 검토한다. 한국어 지원은 선택 모델별로 확인한다. |
| PyMuPDF4LLM | 확인한 변경 이력 1.27.2.2에는 OCR 플러그인 선택 개선, 1.27.2.1에는 Layout 자동 설치·활성화와 정확한 의존성 버전 지정이 있다. 이 페이지에는 출시일이 없어 81일 안의 변경이라고 단정하지 않는다. | CPU 추출·좌표·읽기 순서의 비교 후보. 예전의 순수 규칙 기반 경로와 현재 Layout 경로를 구분한다. |
| olmOCR | 문서 선형화와 공개 OCR 평가 도구를 제공. README의 v0.4.0 모델은 2025-10-21 출시이므로 최근 신규 도구로 소개하지 않는다. | 엔진 전면 도입보다 공개 평가의 항목별 통과/실패 방식을 우선 참고한다. |
| Xberg / Kreuzberg | Rust 기반 범용 문서 처리와 여러 언어 바인딩. 현재 Xberg 저장소와 Kreuzberg LTS 경로를 구분해야 한다. | 대량 처리, 메모리 제한, 외부 런타임 격리 설계 참고 후보. SSD 사양 전용 계층의 직접 대체는 별도 작업이다. |
| MarkItDown | 다양한 형식을 Markdown으로 변환하는 경량 도구. 공식 설명도 고충실도 문서 변환과는 목적 차이가 있음을 밝힌다. | Office 등 입력 형식 확대에는 유용하지만, 이번 기술 표·도식 품질 개선의 우선 후보는 아니다. |

근거: [Docling 릴리스](https://github.com/docling-project/docling/releases/tag/v2.126.0), [Native PDF PR](https://github.com/docling-project/docling/pull/3979), [Marker 2 릴리스](https://github.com/datalab-to/marker/releases/tag/v2.0.0), [MinerU](https://github.com/opendatalab/MinerU), [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), [PyMuPDF4LLM 변경 이력](https://github.com/pymupdf/pymupdf4llm/blob/main/CHANGES.md), [olmOCR](https://github.com/allenai/olmocr), [Xberg](https://github.com/xberg-io/xberg), [Kreuzberg LTS](https://github.com/kreuzberg-dev/kreuzberg-lts/blob/main/CHANGELOG.md), [MarkItDown](https://github.com/microsoft/markitdown).

Docling 파서 7.17.0의 9월 2일 변경은 특정 parse/render 벤치마크에서 최대 3.84배 향상을 보고한다. 이는 본 프로젝트의 전체 변환 속도가 그만큼 빨라진다는 의미가 아니다. [파서 최적화 PR](https://github.com/docling-project/docling-parse/pull/333).

## 공개 벤치마크에서 확인할 수 있는 것

### Marker가 공개한 olmOCR-bench 비교

다음은 Marker 개발팀이 공개한 실행 결과이며 이번에 재현한 수치가 아니다. 동일 표의 도구라도 모델/backend 선택에 따라 결과가 달라진다.

| 설정 | 전체 점수 | 디지털 PDF 점수 | 처리량 |
| --- | ---: | ---: | ---: |
| Marker balanced / GPU | 76.0 | 83.5 | 2.9 page/s |
| Marker fast / GPU | 66.6 | 71.6 | 7.4 page/s |
| MinerU pipeline / GPU | 72.7 | 83.3 | 0.54 page/s |
| Docling standard / GPU | 50.3 | 64.0 | 2.1 page/s |
| Marker fast, OCR 비활성 / CPU | 43.6 | 55.8 | 23.7 page/s |

1,403개 PDF, 8개 범주 평균 점수이며 처리량은 B200 호스트에서 각 도구의 동시성을 활용한 값이다. Mac 단일 문서 지연시간과 직접 비교할 수 없다. MinerU pipeline 결과를 MinerU VLM 최고 품질로 해석해서도 안 된다. [Marker 벤치마크와 재현 안내](https://github.com/datalab-to/marker#benchmarks).

### OmniDocBench의 문서 VLM 비교

조사 시점 README의 **v1.6_full 표**에서 읽은 값이다. README에 다른 평가 버전도 공존하므로 표 이름까지 고정해야 한다.

| 모델 | Overall | 표 TEDS | 텍스트 편집거리: 낮을수록 좋음 |
| --- | ---: | ---: | ---: |
| PaddleOCR-VL-1.6 | 96.34 | 94.7619 | 0.0326 |
| MinerU2.5-Pro | 95.75 | 93.42 | 0.036 |
| GLM-OCR | 95.22 | 92.83 | 0.044 |

이 점수는 텍스트·표·수식 평가를 결합한 지표다. olmOCR-bench의 76.0과 서로 비교하거나, 내부 스코어보드의 100/100과 비교할 수 없다. 참고로 MinerU 논문의 95.69와 현재 README의 95.75도 출처·실행 버전 차이를 유지해야 한다. [OmniDocBench](https://github.com/opendatalab/OmniDocBench), [MinerU2.5-Pro 논문](https://arxiv.org/abs/2604.04771).

## 이번에 직접 수행한 로컬 비교

### 방법

- macOS 26.6.2 / arm64, 동일 Python 3.11 환경.
- `pdf2md 0.1.0`, `pdfplumber 0.11.9`, `pypdf 6.9.2`.
- `Docling 2.103.0`, `docling-core 2.83.0`, `docling-parse 6.2.0`, `torch 2.12.1`. 최신 2.126.0과 native 파이프라인은 미실측이다.
- 입력은 로컬에 있던 NVMe Base 2.3의 앞부분 5페이지, controller 관련 5페이지, SGL 관련 4페이지의 동일한 PDF 조각이다. 페이지 번호는 파일의 물리적 순서 기준이며 문서에 인쇄된 번호와 다르다.
- 각 설정을 최초 1회와 추가 3회 실행했다. 표에는 추가 3회의 중앙값을 제시한다. Docling converter는 재사용했으므로 뒤 구간의 최초 실행은 모델 cold start가 아니다.
- 시간은 변환과 Markdown/JSON/asset 저장을 포함하며 import와 외부 검증기 실행은 제외한다. 최초 모델 초기화 비용은 별도 실행 시간 배열에 남아 있다.
- `pdf2md`: `technical_spec_rag_visual`, `domain_adapter=nvme`, referenced 이미지, page worker 1.
- `Docling`: standard pipeline, CPU 4 threads, 표 인식·그림 이미지 활성화. 디지털 PDF 비교이므로 `do_ocr=False`.
- 추가 실험: pdf2md에서 **figure_region_ocr만 False**로 변경했다. 이는 OCR 비용 분리 실험이며 Visual RAG의 동일 기능을 보장하는 설정이 아니다.

### 처리 시간

| NVMe 구간 | 페이지 | pdf2md Visual 전체 | pdf2md 영역 OCR만 비활성 | Docling 2.103 standard |
| --- | ---: | ---: | ---: | ---: |
| 앞부분 | 5 | 24.163초 | 1.221초 | 13.417초 |
| Controller / 도식 / 표 | 5 | 1.801초 | 0.572초 | 3.629초 |
| SGL / 복잡 표 | 4 | 1.044초 | 0.823초 | 8.199초 |

이 설정에서는 pdf2md가 controller·SGL 구간에서 빠르지만 앞부분의 영역 OCR 비용이 크다. 출력 범위와 CPU 작업자 설정이 같지는 않으므로 엔진 자체의 보편적인 우열로 확대하지 않는다. 전체 문서의 장시간 처리량, peak RSS, GPU 성능은 이번 실험에서 측정하지 않았다.

세 구간 모두 pdf2md의 artifact/index/provenance 검증기는 통과했다. 모든 반복에서 pdf2md Markdown은 동일했고, 영역 OCR 비활성화 전후에도 Markdown 해시가 동일했다. Docling도 실행 폴더가 포함된 이미지 링크를 정규화한 뒤에는 반복 Markdown 해시가 동일했다. 이 결과는 다른 환경의 결정성이나 모든 JSON 파일의 동일성을 입증하지 않는다.

실험 자료: [실행 스크립트](../output/tool_review_20260911/benchmark_local.py), [실측 JSON](../output/tool_review_20260911/benchmark_results.json), [OCR 비용 분리 스크립트](../output/tool_review_20260911/benchmark_ablation.py), [OCR 비용 분리 결과](../output/tool_review_20260911/ablation_results.json). `output/`은 로컬 산출물 경로이며 Git 추적 대상이 아니다.

## 직접 확인한 개선 지점

### 1. 제외된 그림 후보까지 OCR하여 처리량을 낭비한다

앞부분 5페이지의 `figures_rag.jsonl`에는 실제 이미지 5개와 `excluded_image` 154개가 있었다. 영역 OCR은 159개 모두를 처리했고, 결과는 accepted 1개, empty_result 119개, low_confidence 39개였다. 최초 실행에서 그림 단계는 24.086초로 전체 약 25.377초의 대부분이었다.

영역 OCR을 끈 중앙값은 24.163초에서 1.221초로 감소했다. 약 19.8배의 차이는 **기능을 줄인 실험 결과**이며 최적화 후 동일 품질로 달성할 수 있는 속도라고 주장하지 않는다. 원문 Markdown은 그대로였지만 OCR 근거와 그로부터 파생되는 sidecar 내용은 달라질 수 있다.

코드상 `augment_figure_records_with_region_ocr()`는 전달된 모든 레코드에 OCR을 시도하고, `_region_ocr_result()`는 후보마다 전체 페이지를 렌더한 뒤 자른다. Tesseract adapter는 텍스트와 신뢰도에 각각 인식 함수를 호출한다. 개선 후보는 제외 사유별 OCR 대상 판정, 페이지 렌더 재사용, 동일 crop 결과 캐시, 단일 인식 결과에서 원문·신뢰도를 함께 확보하는 경로다. 의미 있는 제외 후보까지 일괄 제거해서는 안 된다.

근거: [영역 OCR 구현](../pdf2md/serializers/rag_figure_semantics.py), [Tesseract adapter](../pdf2md/extractors/ocr_backends/tesseract.py), [최초 실행 보고서](../output/tool_review_20260911/front_matter/pdf2md/run-0/report.json).

### 2. 도식이 빈 HTML 표로 오인된다

controller 구간의 세 번째 페이지, 원문 인쇄 번호 674에는 Figure 729~731 네트워크 도식이 있다. pdf2md는 이 페이지에서 빈 HTML 표 4개를 생성하고 도식의 라벨을 여러 조각으로 본문에 출력했다. Docling은 이 페이지의 도식을 그림 3개로 저장했다.

해당 5페이지에서 pdf2md 표 7개 중 4개는 이 빈 표였고, Docling의 실제 table 객체는 3개였다. 따라서 기존 비교에서 “표 7개 대 3개”를 추출 성능 향상으로 해석하면 반대 결론이 된다. pdf2md는 low-quality table 4개를 기록했지만 actionable warning은 0이었고 세 무결성 검증기는 통과했다.

필요한 개선은 diagram/table 분류, 빈 표 억제, 벡터 그림의 영역 crop, 캡션 연결과 도식 텍스트의 본문 분리다. 이 사례를 실제 PDF 회귀 fixture로 추가하고, 검증기가 빈 표를 검출하도록 해야 한다.

근거: [원문 렌더](../output/tool_review_20260911/controller-diagrams-source.png), [pdf2md 출력](../output/tool_review_20260911/controller_tables/pdf2md/run-3/document.md), [Docling 출력](../output/tool_review_20260911/controller_tables/docling/run-3/document.md).

### 3. HTML fallback만으로 중첩 표 구조가 보존되지는 않는다

SGL 구간 두 번째 페이지의 Figure 118·119는 바깥쪽 Bytes/Description 표의 15번 byte 셀 안에 Bits/Description 표가 들어 있다. pdf2md는 주요 바이트 값과 설명 텍스트를 보존하지만, 내부 표의 07:04·03:00 행을 하나의 셀 문자열로 합쳤다. 이 구간의 low-quality table 수는 0이었다.

Docling 기본 Markdown도 내부 구조를 평평한 행으로 표현하므로 완전한 해결책으로 볼 수 없다. 외부 추출기를 비교할 때 Markdown 외에 셀 좌표, rowspan/colspan, 내부 표의 부모 관계가 담긴 구조화 결과를 함께 평가해야 한다. “표로 출력됨”과 “원본 셀 관계가 맞음”은 별도 지표가 필요하다.

근거: [원문 렌더](../output/tool_review_20260911/sgl-source.png), [pdf2md 출력](../output/tool_review_20260911/sgl_figures_tables/pdf2md/run-3/document.md), [Docling 구조화 출력](../output/tool_review_20260911/sgl_figures_tables/docling/run-3/document.json).

### 4. 현재 벤치마크는 객관적 정확도를 충분히 측정하지 않는다

- [내부 스코어보드](QUALITY_SCORECARD.md)의 100/100은 자체 기준의 기능·운영 완료도다. 공개 문서 정확도 100%가 아니다.
- [기존 Docling 비교 스크립트](../scripts/benchmark_docling_comparison.py)는 Docling의 실제 table 객체 수 대신 `table`을 포함한 JSON 키 개수를 센다. 그림 개수도 유사한 방식이다.
- 같은 스크립트에서 `pages`는 pdf2md 측에만 전달되므로 원본 전체 PDF와 범위 옵션을 함께 쓰면 입력이 불공정해질 수 있다. 기존의 별도 PDF 조각 비교는 이 특정 문제를 피하지만, 키 개수 문제는 남는다.
- 기존 시간 측정은 pdf2md 변환·저장과 Docling `convert()` 구간이 달라 직접 비교에 제약이 있다.
- 프로필명을 `Config`에 넣는 것만으로 전체 프리셋 옵션이 적용되지는 않는다. 기존 스크립트는 옵션 일부를 직접 지정하므로 CLI의 동일 이름 프로필과 다를 수 있다. 이번 실험은 `rag_profile_options()`를 명시적으로 적용했다.
- [RAG 평가](../scripts/run_rag_eval.py)는 영문·숫자 토큰의 겹침을 사용하는 로컬 smoke 점수다. 한국어 토큰을 일반적으로 평가하지 못하며 실제 임베딩 검색이나 reranker 품질을 검증하지 않는다.

## 유지할 부분과 도입을 검토할 부분

유지할 부분은 `manifest/report`, 안정적인 source ID, 요구사항 추적, NVMe/OCP/보안 도메인 단위, 원문과 생성 설명의 분리, 페이지 단위 부분 실패 처리다. 범용 도구의 Markdown/JSON을 받아도 이 프로젝트의 전용 계약으로 매핑하는 작업은 여전히 필요하다.

도입 검토는 문서 전체 교체보다 페이지·영역별로 제한한다. 기존 IR에 출처가 명확한 외부 후보를 연결하고, 문자·숫자·부정어 보존 및 셀 관계 검증을 통과한 것만 채택하는 방식이 적합하다. 외부 모델 출력에는 backend/version/model revision, bbox 변환, 채택·거절 사유를 남겨야 한다.

이는 현재 [Native Migration 방침](PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md)의 외부 backend 비채택 결정을 재검토하자는 제안이다. 이번 조사에서 운영 방침을 바꾸지는 않았다.

배포 검토 시 라이선스도 버전별로 구분한다. Marker 코드는 Apache-2.0이지만 가중치에는 별도 조건이 있고, MinerU는 추가 조건이 있는 자체 라이선스다. PyMuPDF4LLM 저장소는 AGPL-3.0으로 표시된다. [Marker 안내](https://github.com/datalab-to/marker#commercial-usage), [MinerU 라이선스](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md), [PyMuPDF4LLM](https://github.com/pymupdf/pymupdf4llm).

## 제안하는 우선순위와 승인 기준

| 순서 | 작업 | 완료 판단 기준 |
| --- | --- | --- |
| 1 | 이번 OCR 병목·빈 표·중첩 표 사례를 평가 corpus에 추가 | 정상 원문과 실패 위치를 수동 검토한 정답으로 고정. 기존 golden 재생과 별도로 평가 |
| 2 | 영역 OCR 선별 및 페이지 렌더 재사용 | 원문·승인된 OCR 근거가 유지되는지 확인하고 OCR 호출 수, 중앙값, p95, 메모리 절감을 실측 |
| 3 | 도식/표 구분과 중첩 표 표현 보강 | 빈 표 0개, 검토한 벡터 도식의 이미지/캡션 연결, 내부 셀 관계 보존 확인 |
| 4 | 동일 조건 비교 실행기 정비 | 입력 hash·페이지·실효 옵션·모델 revision·하드웨어·초기화/변환/저장 시간을 기록하고 실제 객체 수 집계 |
| 5 | Docling 최신 standard, Marker fast/balanced, MinerU 또는 PaddleOCR를 선택적 후보로 비교 | 어려운 표/OCR 영역에서 정답 기준 향상이 입증될 때만 선택적 adapter 검토 |
| 6 | 한국어 및 실제 RAG 평가 확대 | 한국어·영문 질문, 부정어·비트 범위·단위·요구사항 ID, 검색 근거 정확도를 독립 측정 |

공통 비교 corpus는 예를 들어 100~200페이지의 별도 검증 세트로 시작한다. 디지털 단일/다단, 한국어/영문, 스캔, 병합/중첩/연속 표, 벡터 도식, 수식을 나누고 개발 중 튜닝에 쓰지 않은 문서를 포함한다. 이는 제안 규모이며 이번에 실행한 양이 아니다.

측정 지표는 텍스트 CER와 중요 토큰 정확 일치, 표 TEDS/TEDS-S와 셀 매핑, 읽기 순서 오류, 그림 bbox/캡션 연결, 요구사항 precision/recall, RAG Recall@k/MRR/인용 정확도, 실행시간·peak RSS·모델 크기를 분리한다. `shall not`, `0h`, `00b`, bit range와 단위의 손실은 전체 평균으로 숨기지 않는다. 공개 benchmark와 프로젝트 전용 정답 세트의 결과를 별도 표로 유지한다.

## 검증 상태

실측 변환 3구간과 OCR 비용 분리 실험을 완료했고, 각 구간의 최종 pdf2md 산출물은 artifact/index/provenance 검증을 통과했다. PDF 원문을 렌더해 도식 오인과 중첩 표 손실을 확인했다. 운영 변환 코드와 의존성은 변경하지 않았다.

추가로 다음 기존 테스트 52개가 19.29초에 모두 통과했다. 전체 테스트 스위트를 실행한 것은 아니다. 실제 발견한 문제와 기존 테스트 통과가 동시에 성립하므로, 이번 실제 PDF 사례를 추가한 평가가 필요하다.

```bash
.venv311/bin/python -m pytest \
  tests/test_golden_corpus.py tests/test_rag_figures.py \
  tests/test_pipeline_smoke.py tests/test_cli.py
```
