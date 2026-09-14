# Q156 비교 벤치마크 공정성

2026-09-14 구현 및 로컬 검증 완료. 커밋·PR merge 전 상태다.

## 실행 계약

`scripts/benchmark_fair_comparison.py`가 Q156부터 성능 계측의 기준 진입점이다.
기존 `benchmark_docling_comparison.py`는 이전 artifact 비교 계약을 유지하는 legacy 경로이며,
페이지 선택·시간 범위가 다른 기존 성능 숫자로 도구 우열을 판단하지 않는다. CLI help와 scorecard에도 표시한다.

새 실행기는 페이지 선택을 한 번만 수행해 `input.pdf`를 만들고 모든 engine에 동일 파일을 전달한다.
원본·slice SHA-256, 원본 페이지 목록, 각 자식 프로세스에서 읽은 hash를 기록한다.
기존 출력 디렉터리는 덮어쓰지 않는다. 엔진은 순차적으로 독립 Python 프로세스에서 실행한다.

각 엔진은 import → 설정·모델 로딩 → cold 1회 → warm 5회를 실행한다.
변환과 Markdown/JSON export·파일 저장은 모두 같은 계측 구간에 들어간다.
입력 준비, import, setup, 전체 프로세스 wall time은 별도 필드이며 검사·통계 계산은 변환 시간 밖이다.
Cold는 명시적 모델 초기화 후 첫 변환이다. OS 파일 캐시를 비우는 실험을 의미하지 않는다.
Warm은 같은 프로세스·엔진을 재사용하되 각 회차를 새로운 출력 디렉터리에 저장한다.

성공한 warm 5회가 모두 있어야 중앙값·최솟값·최댓값을 제공한다.
부분 성공·실패가 섞이면 누락된 표본을 숨기지 않고 median을 null로 남긴다. p95는 보고하지 않는다.
전체 6회 성공과 입력 hash 일치를 확인해야 `timing_samples_complete=true`가 된다.
이 값은 기능 동등성이나 원문 품질 통과를 뜻하지 않는다.

## 옵션·버전·메모리

- Native는 실제 CLI parser와 config 생성 경로를 사용하여 프로필의 유효 옵션을 적용한다. Config와 각 manifest의 유효 옵션을 모두 기록한다. Native 페이지 worker는 1개다.
- Docling은 `initialize_pipeline`을 setup에서 실행하고 `document.tables`, `document.pictures`, `document.pages`의 실제 길이를 센다. JSON 키 이름의 출현 빈도는 사용하지 않는다.
- Docling의 CPU device와 thread 수를 명시하고, 두 프로세스에 OMP/BLAS thread 환경 변수를 적용한다. Native와 Docling의 알고리즘·OCR·sidecar 기능이 같다고 가정하지 않는다.
- 패키지·Python·플랫폼 버전, native Python 소스 hash, 사전 배치한 Docling 모델 파일 트리 hash를 기록한다. Tesseract 실행 파일 버전과 확인 가능한 영어 traineddata hash도 기록한다. 확인 불가 값은 null이다.
- Peak RSS는 engine 프로세스 수명 전체의 high-water mark이며 import·모델 로딩을 포함한다. 자식 OCR 프로세스 메모리는 제외된다. `resource` 미지원 플랫폼은 null과 unavailable scope를 기록한다. 이 제한을 무시한 메모리 우열은 판단하지 않는다.

모델 다운로드는 벤치마크에서 실행하지 않는다. Docling 모델을 사전에 배치하고 경로를 지정해야 한다.
HF offline 모드, 로컬 artifacts, remote service 비활성화, Tesseract CLI OCR을 사용한다.
설치·로컬 모델·호환 API가 없으면 단계와 예외 종류를 기록한다. 설치와 버전별 실험은 Q157 범위다.
모델 다운로드 시간은 측정하지 않았으므로 0초가 아닌 null로 기록한다.

## 사용법

```bash
.venv311/bin/python scripts/benchmark_fair_comparison.py \
  --input-pdf /absolute/path/source.pdf --pages 3-4 \
  --output-dir output/fair-benchmark-new \
  --native-profile technical_spec_rag_visual --domain-adapter nvme \
  --threads 4 --docling-python /absolute/path/docling-env/bin/python \
  --docling-models /absolute/path/preprovisioned-models
```

Native만 검증할 때는 `--engines native`를 지정한다. 기본은 native와 docling이다.
새 `fair_benchmark_report.json`과 engine별 cold/warm 산출물을 저장한다.
`*.request.json`, `*.result.json`, PDF와 실제 텍스트는 로컬 검증용이며 원문 경로를 포함할 수 있다.
공유 시 원문 없는 집계만 선택한다. 전체 측정 성공은 종료 코드 0, 실행 실패·미설치는 2다.

처리량은 각 표본의 처리 페이지 / convert+export+write 초다.
원문 품질은 별도 Q152 정답 검사를 사용하며 기본 보고서는 `not_evaluated`다.
Native sidecar가 없는 외부 도구는 `unsupported` 기능으로 표시하고 품질 0점으로 환산하지 않는다.
공통 기능을 맞추는 최종 비교 설정과 외부 도구의 source-quality 어댑터는 Q157에서 확정한다.

## 근거와 검증

Docling setup·로컬 artifact 경로·OCR 설정은 [공식 FAQ](https://docling-project.github.io/docling/faq/),
[DocumentConverter API](https://docling-project.github.io/docling/reference/document_converter/),
[Pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/)를 확인했다.
실제 외부 패키지로의 동작 확인은 Q157에 남아 있으며 이번 API 테스트는 모의 객체를 사용한다.

회귀 검사는 실제 native 자식 프로세스와 페이지 slice, CLI 프로필 적용, 6회 실행,
Docling 객체 수 집계, setup/convert/export 경계, 실패 export, 미설치, timeout,
입력 hash 불일치, 출력 덮어쓰기 거부, 모델 변경 식별을 포함한다.
실제 controller slice의 두 페이지로 native를 실행한 결과와 Docling 모델 경로 미지정 상태도 로컬에 기록했다.
현재 설치된 Docling은 2.103.0이며 import까지 확인했다. 지정 버전의 실제 변환 실험은 Q157에서 수행한다.

전체 unit/integration/CLI/golden **575개**, Ruff, schema 동기화와 CLI help 검사가 통과했다.
Q156 전용 테스트 9개를 포함하며 기존 golden 파일은 변경하지 않았다.
최종 native 2페이지 smoke에서 warm 중앙값 0.972초, 범위 0.947–0.995초를 기록했다.
Docling은 `unavailable`, `local_model_directory_required`로 기록하여 전체 비교 완료를 false로 유지했다.
이 수치는 계측기 동작 확인용이며 속도 우열의 근거가 아니다.
[원문 없는 검증 집계](evaluation/q156_validation_2026-09-14.json)를 함께 보관한다.
