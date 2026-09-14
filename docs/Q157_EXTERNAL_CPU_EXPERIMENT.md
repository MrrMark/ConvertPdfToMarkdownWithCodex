# Q157 외부 CPU 도구 비교 실험

## 범위와 재현

Q152의 로컬 NVMe corpus 세 사례(5/5/4페이지)를 고정 버전으로 비교한다.
원문 PDF·정답·변환 산출물은 `output/`에만 보관하며 제품 backend는 변경하지 않는다.

| 엔진 | 고정 배포판 | 실행 설정 |
| --- | --- | --- |
| Native | 현재 소스 SHA256 tree 및 freeze 기록 | `technical_spec_rag_visual`, domain `none`, page worker 1 |
| Docling | `docling==2.126.0` | 로컬 layout/tableformer, CPU 4 threads, Tesseract CLI 영어 |
| PyMuPDF4LLM | `pymupdf4llm==1.27.2.2` | 기본 layout 활성, 이미지 저장, 영어 OCR, ONNX CPU 4 threads |
| Marker | `marker-pdf==2.0.0` | fast 실행 전 로컬 VLM prerequisite 검사 |

각 도구는 별도 Python 3.11 환경에 설치했다. 설치된 전체 의존성은 실행 디렉터리의
`*.freeze.txt`에 기록하며 지정 배포판 버전이 다르면 변환을 시작하지 않는다.
공식 배포 정보: [Docling](https://pypi.org/project/docling/2.126.0/),
[Marker](https://pypi.org/project/marker-pdf/2.0.0/),
[PyMuPDF4LLM](https://pypi.org/project/pymupdf4llm/1.27.2.2/).

모델은 입력 PDF 없이 미리 다운로드했다. 변환 프로세스에는 Hugging Face/Transformers offline을 지정한다.
Docling은 remote services를 끄고 로컬 artifacts를 전달한다. PyMuPDF layout은 패키지에 포함된 모델을 쓴다.
Marker는 로컬 `llama-server` 부재로 실행하지 않았다. fast에서도 VLM이 호출될 수 있으므로
`disable_ocr`로 바꾼 결과를 fast 기본 비교로 대체하지 않는다.
CPU 서버와 가중치를 준비한 후 Marker 실행 어댑터를 완성하는 작업은 별도로 남는다.
설정 근거는 [Marker 공식 README](https://github.com/datalab-to/marker),
[Docling API](https://docling-project.github.io/docling/reference/document_converter/),
[PyMuPDF4LLM API](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html) 및 설치된 고정 버전 소스다.

```bash
.venv311/bin/python -m venv output/q157_envs/docling
.venv311/bin/python -m venv output/q157_envs/marker
.venv311/bin/python -m venv output/q157_envs/pymupdf
output/q157_envs/docling/bin/python -m pip install -r docs/evaluation/q157_docling_freeze.txt
output/q157_envs/marker/bin/python -m pip install -r docs/evaluation/q157_marker_freeze.txt
output/q157_envs/pymupdf/bin/python -m pip install -r docs/evaluation/q157_pymupdf_freeze.txt
HF_HOME="$PWD/output/q157_models/hf" output/q157_envs/docling/bin/docling-tools models download layout tableformer --output-dir output/q157_models/docling
.venv311/bin/python scripts/benchmark_q157_corpus.py --output-dir output/q157_cpu_final
```

위 환경 lock은 이 Mac/Python 조합에서 수집한 것이므로 다른 플랫폼의 설치 성공을 보장하지 않는다.
모델 다운로드의 upstream 기본 revision은 변할 수 있다. 같은 결과를 재현하려면 보고서에 기록된
모델 tree hash와 대조하고 기존 로컬 모델을 보존해야 한다.

기존 결과 집계만 다시 생성할 때는 `--collect-only`를 추가한다. 일반 실행은 출력 덮어쓰기를 거부한다.
경로는 `--corpus-dir`, `--truth-dir`, `--env-dir`, `--models`로 지정할 수 있다.
기존 Q156 단일 사례 CLI에도 `--fixed-external-versions`, `--pymupdf-python`, `--marker-python`을 추가했다.

## 측정 경계

- 같은 입력 바이트를 엔진별 독립 프로세스에 전달하고 cold 1회, 같은 프로세스 warm 5회를 순차 실행한다.
- 전체 페이지 corpus는 원본을 byte copy한다. 일부 페이지 선택에만 pypdf slice를 사용한다.
  front matter의 불필요한 PDF 재작성에서 재귀 오류가 발생한 문제를 이 방법으로 해소했다.
- 변환·export·파일 쓰기를 함께 측정하며 import/모델 초기화/입력 준비 비용은 분리한다.
  PyMuPDF layout 모델은 import 시 초기화되므로 `import_seconds`에 포함된다.
- PyMuPDF의 고정 버전 API는 ONNX 세션 옵션을 받지 않는다. 격리 worker의 import 동안만
  세션 생성에 CPU provider 및 intra 4/inter 1 thread를 전달하고 원래 생성자를 복원한다.
- warm 5회가 모두 성공해야 중앙값/최소/최대가 나온다. 실패·미지원 결과는 속도 0으로 바꾸지 않는다.
- RSS는 엔진 프로세스 전체 수명의 최댓값이며 OCR 등 자식 프로세스 메모리는 포함하지 않는다.
- export 범위는 다르다. Native는 RAG sidecar까지, Docling은 Markdown/document JSON,
  PyMuPDF는 Markdown/page JSON/이미지를 쓴다. 표·그림 수 역시 각 도구 객체 정의에 따른 관찰값이다.
  따라서 속도만으로 동등 품질이나 대체 가능성을 주장하지 않는다.

## 품질 해석

`summary.json`의 `source_token_smoke`는 기존 원문 검토 정답에 있는 토큰이 최종 Markdown에
존재하는지를 문서 전체에서 확인한다. 공백과 HTML entity만 정리하고 토큰을 교정하지 않는다.
페이지·셀 위치, 순서, nested table 구조, 그림 bbox 정확도는 이 점수에 포함하지 않는다.
외부 도구가 Native sidecar를 제공하지 않는 것은 `unsupported`이며 품질 0점이 아니다.
정답 원문 대신 check ID와 토큰 개수만 공유 가능한 집계에 남긴다.

## 실행 결과

2026-09-14 macOS 26.6.2 arm64 / Python 3.11.15에서 실행했다.
Native·Docling·PyMuPDF4LLM은 사례마다 cold 1 + warm 5회 모두 성공했다(총 54회).
Marker는 세 사례 모두 `marker_fast_requires_local_llama_server_missing`이며 시간 비교에서 제외했다.
따라서 요청한 모든 엔진의 성공을 뜻하는 `timing_samples_complete`는 false다.
실행 불가 사유까지 기록하는 Q157 실험 완료 기준과 이 필드는 별개다.

아래 값은 warm 5회 중앙값(초)이다.

| 사례 | 페이지 | Native | Docling 2.126.0 | PyMuPDF4LLM 1.27.2.2 |
| --- | ---: | ---: | ---: | ---: |
| Front matter | 5 | 1.843 | 14.277 | 4.326 |
| Controller tables | 5 | 1.352 | 4.911 | 1.914 |
| SGL figures/tables | 4 | 1.086 | 13.842 | 1.537 |

프로세스 peak RSS는 사례별 Native 약 203–243 MiB, Docling 약 2,132–2,286 MiB,
PyMuPDF 약 477–531 MiB였다. import/초기화도 포함하며 자식 OCR 프로세스는 제외한다.
이번 corpus와 설정에서는 Native가 속도·프로세스 메모리에서 유리했다.
세 사례만으로 다른 문서군·플랫폼의 성능을 일반화할 수는 없다.

품질 관찰 결과는 다음과 같다.

- 모든 실행 가능한 엔진이 선택 원문 토큰 smoke를 통과했다. 이는 문서 전체의 토큰 존재 검사다.
- Native는 기존 Q155 원문 정답 검사도 세 사례 모두 `quality_passed=true`, `gate_passed=true`다.
- Controller 실제 표 3개를 Native와 Docling은 표 객체로 출력했다. PyMuPDF는 표 객체 0개이며,
  해당 본문을 확인하면 프로토콜/서브타입/도메인 표가 문단으로 이어져 있다. 토큰 통과와 구조 보존은 다르다.
- SGL의 Figure 118/119에서 Native는 Q155의 중첩 HTML 표 검사를 통과했다.
  Docling은 내부 bit 행을 바깥 표의 반복 byte 행으로 펼쳤고, PyMuPDF는 셀 내부 줄바꿈과
  추가 열/행으로 표현했다. 두 도구의 Markdown은 Native와 같은 중첩 표 계층을 제공하지 않았다.
- Front matter의 Docling `tables` 컬렉션 2개에는 `document_index` 라벨이 포함된다.
  PyMuPDF는 3개 layout table box를 기록했다. 이 수치를 그대로 오탐 개수나 표 정확도로 해석하지 않는다.
- Docling 기본 Markdown export는 그림 placeholder를 사용한다. 이번 설정으로 Native의 referenced
  이미지 저장이나 RAG sidecar 기능까지 동등하다고 주장하지 않는다.

따라서 현재 기본 backend는 유지하는 것을 권장한다. Docling의 구조 객체/표 모델은 향후 어려운 표의
선택적 fallback 후보로 검토할 수 있지만, 이번 결과만으로 도입 효과는 입증되지 않았다.
PyMuPDF는 단순 텍스트·이미지 처리 후보로 남기되 기술 표 보존 검증 없이 교체하지 않는다.
우선 다음 계획인 Q158 한·영 검색 평가를 진행하고 Q159 visual 참조 계약 문제를 해결한다.
외부 도구 채택을 다시 검토할 때는 스캔·한글·복잡 표의 별도 원문 정답과 Marker CPU 런타임을 준비한다.

## 산출물과 검증

- [공유 가능한 실측 집계](evaluation/q157_cpu_2026-09-14.json): 입력 hash, 버전, 모델 hash,
  전체 timing 표본, RSS, 선택 토큰 개수, 실행 불가 사유. PDF/원문 토큰/로컬 경로는 제외한다.
- [Docling freeze](evaluation/q157_docling_freeze.txt), [Marker freeze](evaluation/q157_marker_freeze.txt),
  [PyMuPDF freeze](evaluation/q157_pymupdf_freeze.txt): 실제 설치된 전체 의존성 버전.
- 로컬 `output/q157_cpu_final/`: 공통 입력, 모든 cold/warm 산출물, 전체 옵션을 포함한 엔진 보고서,
  `summary.json`, `native_source_quality.json`, Native 포함 환경 freeze.
- `scripts/benchmark_external_cpu.py`: PyMuPDF CPU 어댑터와 Marker prerequisite 검사.
- `scripts/benchmark_q157_corpus.py`: corpus hash 검증, 순차 실행, 별도 토큰 smoke와 공개 집계.

전체 unit/integration/CLI/golden **582개 통과**. 신규 7개 테스트는 버전 불일치,
Marker 런타임 부재, 실제 box 집계, 토큰/구조 평가 경계, truth hash 불일치,
전체 PDF 바이트 보존, 공개 집계의 경로/원문 제외를 검증한다.
Ruff·schema 동기화·CLI help 검사를 수행했으며 기존 golden은 변경하지 않았다.
Q156/Q157은 2026-09-15 PR #142, merge commit `9e004e5`로 main에 반영했다.
