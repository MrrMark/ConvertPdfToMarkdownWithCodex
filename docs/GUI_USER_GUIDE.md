# GUI 사용자 가이드

이 문서는 CLI가 익숙하지 않은 사용자가 `pdf2md` GUI만 보고 PDF를 Markdown으로 변환할 수 있도록 정리한 별도 사용자 가이드다.

자동화, CI, 반복 스크립트 실행은 GUI보다 CLI를 권장한다. GUI는 파일 또는 폴더를 직접 선택해 한 번씩 변환하고 결과를 확인하는 사용자를 위한 간편 실행 화면이다.

## 1) GUI 실행

설치와 가상환경 준비가 끝난 상태에서 아래 중 하나로 실행한다.

```bash
python -m pdf2md.gui
```

```bash
pdf2md-gui
```

도움말 smoke는 아래 명령으로 확인한다. 이 명령은 GUI 창을 열지 않고 도움말만 출력한다.

```bash
python -m pdf2md.gui --help
```

runtime doctor는 아래 명령으로 확인한다. 이 명령은 Tcl/Tk patchlevel, display/window advisory, OCR/Tesseract, Pillow/pypdfium2, help document, source/editable/wheel packaging mode를 구조화된 진단으로 출력한다.

```bash
python -m pdf2md.gui --doctor
```

실제 Tk window 생성/파괴 probe까지 확인해야 하는 desktop session에서는 아래처럼 명시한다.

```bash
python -m pdf2md.gui --doctor --doctor-check-window
```

자동화에서 읽기 쉬운 JSON이 필요하면:

```bash
python -m pdf2md.gui --doctor --doctor-format json
```

운영체제별 설치/실행 준비는 다음 문서를 참고한다.

- macOS: `docs/MACOS_GUI_QUICKSTART.md`
- Windows 빠른 시작: `docs/WINDOWS_INSTALL_RUN_QUICKSTART.md`
- Windows 상세 운영: `docs/WINDOWS_A_TO_Z_GUIDE.md`

## 2) 화면 구성

### Language

- 기본 언어는 한국어다.
- `English`를 선택하면 주요 label, button, status 문구가 영어로 바뀐다.
- 언어 선택은 local-only JSON state에 저장되며 변환 산출물에는 영향을 주지 않는다.

### Preset

- `기본 모드(원본 유지)`: 원문 보존을 우선하는 보수적 기본값이다.
- `RAG 등록용(최적화)`: Markdown 원문을 임의로 바꾸지 않고 RAG table sidecar, page marker, header/footer 보정, hyphenation 보정, table context `embedding_text`, sibling chunk merge, relationship metadata 같은 RAG 친화 옵션을 켠다.
- `기술 스펙 RAG`: storage/PCIe/security spec ingest를 위해 RAG sidecar와 chunk 보강 옵션을 켠다. NVMe/PCIe/OCP/TCG/SPDM 같은 도메인 adapter는 필요에 따라 별도로 선택한다.
- `이미지 업로드 불가 RAG 대응`: GUI 전용 조합이다. 내부 profile은 `technical_spec_rag`를 사용하고, 이미지 파일을 만들지 않는 `placeholder` mode와 `figure_text` retrieval chunk를 함께 켠다. PNG/JPG를 팀 RAG에 올릴 수 없는 기술 스펙 문서에 사용한다.
- `민감정보 보호 RAG`: confidential-safe mode와 sanitized report를 켜고, 공유용 RAG JSONL sidecar 중심으로 산출한다.
- `원본 유지 + sidecar`: Markdown 본문 변화 가능성이 있는 보정은 끄고 RAG JSONL sidecar와 relationship metadata만 추가한다.
- `Optimize Options(유저 선택)`: image/table/RAG/domain과 상세 flag를 직접 고른다.
- `Pages`, `Password`, `OCR lang`, 입력/출력 경로는 preset을 바꿔도 유지된다.
- `기술 스펙 RAG`와 `이미지 업로드 불가 RAG 대응`에서는 `Domain`과 manual domain 입력값을 바꿀 수 있다. 나머지 `custom`이 아닌 preset에서는 세부 변환 옵션이 읽기 전용으로 표시된다.

### Input

- `PDF file`: PDF 파일 하나를 변환한다.
- `PDF folder`: 선택한 폴더 바로 아래에 있는 PDF 파일들을 배치 변환한다.
- `Browse`: 입력 파일 또는 폴더를 선택한다.

### Output folder

- 비워 두면 기본 출력 폴더가 사용된다.
- 단일 파일 변환 기본값은 입력 PDF 옆의 `<pdf_stem>_output` 폴더다.
- 폴더 배치 변환 기본값은 입력 폴더 아래의 `output` 폴더다.
- 권한 오류가 나면 Desktop, Documents, Downloads 같은 쓰기 가능한 사용자 폴더를 선택한다.

### Options

- `Pages`: 변환할 페이지 범위다. 예: `1-3,5`
- `Password`: 암호화된 PDF의 비밀번호다.
- `OCR lang`: OCR 언어 코드다. 예: `eng`, `kor+eng`
- `Image`: 이미지 출력 방식이다. 기본값은 `referenced`다.
- `Table`: 표 출력 방식이다. 기본값은 `auto`다.
- `RAG tables`: RAG table sidecar 출력 방식이다.
- `Domain`: NVMe, PCIe, OCP, TCG, SPDM, customer requirements, manual 같은 도메인 adapter 선택이다.
- `Manual domain label`: `Domain=manual`일 때 `domain_units_rag.jsonl`의 `adapter_profile`에 기록할 사용자 정의 라벨이다. 예: `Customer A Requirements`
- `Manual domain keywords`: `Domain=manual`일 때 표 header 인식에 추가할 키워드다. 쉼표, 세미콜론, 줄바꿈으로 구분한다. 예: `Customer Key, Customer Requirement`

### Flags

- `Skip existing`: 배치 변환에서 기존 Markdown, manifest, report가 있으면 건너뛴다.
- `Confidential safe`: 공개 공유용 metadata에서 민감한 경로/파일명 노출을 줄인다.
- `Force OCR`: 텍스트 layer가 있어도 OCR을 강제로 시도한다.
- `Page markers`: Markdown에 page marker를 남긴다.
- `Remove header/footer`: 반복 header/footer를 보수적으로 제거한다.
- `Dedupe images`: 같은 이미지 객체를 중복 저장하지 않는다.
- `Repair hyphenation`: 명확한 줄바꿈 hyphenation을 복구한다.
- `Figure crop fallback`: caption이 있는 figure에 embedded image가 없을 때 page crop fallback을 시도한다.

### Expert options

- `Page workers`: 페이지 단위 병렬 처리 worker 수다. 1 이상의 정수만 허용한다.
- `Debug artifacts`: 디버그 산출물을 함께 생성한다.
- `Verbose logs`: 더 자세한 실행 로그를 사용한다.
- Expert options는 `Optimize Options(유저 선택)` preset에서 편집 가능하다.

### Profiles

- `Export profile`: 현재 변환 option을 local-only profile JSON으로 저장한다.
- `Import profile`: 저장된 profile JSON을 불러와 option을 적용한다.
- profile은 password, input/output path, 원문 PDF 텍스트, Markdown 본문, 표 내용, 이미지 내용을 저장하지 않는다.
- profile import는 현재 화면의 password처럼 profile에 저장하지 않는 값을 유지하면서 option만 바꾼다.
- invalid profile은 구조화된 GUI diagnostic으로 표시된다.

### Progress

- 단일 PDF 변환은 처리 중임을 나타내는 indeterminate progress로 표시된다.
- 폴더 배치 변환은 현재 문서 index/total과 percent text를 함께 표시한다. 예: `2/10 (20%)`
- 단일 PDF는 실제 page-level 진행률 callback이 들어올 때만 `Page 1/3 (33%)` 같은 percent로 전환한다. callback이 없을 때는 실제 page 처리율처럼 보이는 임의 진행률을 표시하지 않는다.
- 단일 PDF는 완료 시에만 `100%`가 표시된다.

### Layout

- GUI 본문은 작은 화면에서도 세로 스크롤로 주요 입력, 옵션, 결과, 로그 영역에 접근할 수 있다.
- 긴 한국어/영문 preset과 action label은 줄바꿈 가능한 배치로 표시된다.
- Results 표의 긴 Markdown/report 경로는 horizontal scrollbar로 확인할 수 있다.

## 3) 단일 PDF 변환

1. `PDF file`을 선택한다.
2. `Browse`로 PDF 파일을 선택한다.
3. 필요하면 `Output folder`를 선택한다.
4. 목적에 맞는 preset을 선택하고, 필요하면 `Optimize Options(유저 선택)`에서 option과 flag를 조정한다.
5. `Start conversion`을 누른다.
6. 완료 후 Results 표에서 `Status`, `Warnings`, `Markdown`, `Report`를 확인한다.

PNG/JPG 같은 이미지 asset을 업로드할 수 없는 팀 RAG라면 `이미지 업로드 불가 RAG 대응` preset을 선택한다. 이 preset은 `document.md`에 image placeholder만 남기고, `figures_rag.jsonl`과 `retrieval_chunks_rag.jsonl`의 `chunk_type="figure_text"` record로 그림 주변의 관측 텍스트 provenance를 보존한다. 도메인 분류가 필요하면 같은 화면에서 `Domain`을 `nvme`, `pcie`, `spdm`, `manual` 등으로 지정한다.

회로도, 파형, 블록다이어그램처럼 의미가 그림 내부에 주로 있는 문서는 `Optimize Options(유저 선택)`에서 `Figure region OCR`, `Generated figure descriptions`, `Figure structure extraction`을 추가로 켠다. `Figure region OCR`은 figure bbox 영역을 로컬 OCR로 시도하고 결과를 `figures_rag.jsonl`의 diagnostics에만 기록한다. 원문 Markdown이나 text extraction 출력은 바꾸지 않는다. `Generated figure descriptions`와 `Figure structure extraction`은 여전히 deterministic context-only 방식이며 `figure_descriptions_rag.jsonl`, `figure_structures_rag.jsonl`, `retrieval_chunks_rag.jsonl`의 `figure_description`/`figure_structure` chunk로만 보강 정보를 기록한다.

## 4) 폴더 배치 변환

1. `PDF folder`를 선택한다.
2. PDF 파일들이 들어 있는 폴더를 선택한다.
3. 이미 변환된 문서를 건너뛰려면 `Optimize Options(유저 선택)`에서 `Skip existing`을 켠다.
4. 이전 batch와 비교하려면 `Previous corpus manifest`에서 이전 `corpus_manifest.json`을 선택한다.
5. 변경 없는 PDF 산출물을 재사용하려면 `Reuse unchanged`를 켠다.
6. `Start conversion`을 누른다.
7. 중간에 멈추려면 `Cancel`을 누른다.

취소는 문서 경계에서 처리된다. 현재 처리 중인 PDF는 가능한 한 끝까지 처리하고, 아직 시작하지 않은 PDF는 `cancelled` 상태로 기록한다.
이전 manifest를 선택하면 GUI도 CLI batch와 같은 `corpus_diff_report.json`, `requirement_change_impact_report.json`을 생성한다.

## 5) Results 표 읽기

GUI 완료 후 Results 표에서 문서별 결과를 확인한다.

| 열 | 의미 |
|---|---|
| `Document` | 입력 PDF 파일명 |
| `Status` | 변환 상태 |
| `Warnings` | warning 개수와 warning code |
| `Retry` | 실패 후 재시도 후보 여부 |
| `Markdown` | 생성된 Markdown 경로 |
| `Report` | `report.json` 경로 |

완료 summary/log에는 `documents`, status count, retry candidate count, `elapsed_ms`, `processed_pages`, `pages_per_second`가 표시된다. 상세 품질 판단은 `report.json`과 `manifest.json`에서 확인한다. GUI summary는 원문 텍스트, 표, 이미지 내용을 요약하거나 재서술하지 않는다.

결과 행을 선택하면 `Open Markdown`, `Open Report`, `Open Manifest`, `Open Assets`, `Open output folder`로 해당 산출물을 바로 열 수 있다. 폴더 배치 산출물은 `Open Corpus Manifest`, `Open Corpus Diff`, `Open Requirement Impact`로 열 수 있다. 경로가 없거나 OS가 열 수 없는 경우에는 변환 실패가 아니라 GUI warning/log로만 표시된다.

## 6) Status 의미

- `success`: 변환이 정상 완료됐다.
- `partial_success`: 변환은 완료됐지만 actionable warning이나 저품질 표 진단이 있다. 의도된 복잡 표 HTML fallback은 `report.json`의 advisory/expected fallback count에 남지만 그 자체만으로 partial status가 되지는 않는다.
- `failed`: 해당 문서 변환에 실패했다. `Retry`가 표시되면 입력과 옵션을 확인한 뒤 다시 실행한다.
- `skipped`: `Skip existing` 조건에 맞아 건너뛰었다.
- `cancelled`: 배치 변환 중 취소 요청으로 아직 시작하지 않은 문서가 취소됐다.

## 7) 버튼 동작

- `Start conversion`: 현재 입력과 옵션으로 변환을 시작한다.
- `Cancel`: 배치 변환 중 현재 문서가 끝난 뒤 남은 문서를 취소한다.
- `Open Markdown`: 선택한 결과 행의 Markdown 파일을 연다.
- `Open Report`: 선택한 결과 행의 `report.json`을 연다.
- `Open Manifest`: 선택한 결과 행의 `manifest.json`을 연다.
- `Open Assets`: 선택한 결과 행의 assets 폴더를 연다.
- `Open Corpus Manifest`: 폴더 배치의 `corpus_manifest.json`을 연다.
- `Open Corpus Diff`: 이전 manifest를 사용한 폴더 배치의 `corpus_diff_report.json`을 연다.
- `Open Requirement Impact`: 이전 manifest를 사용한 폴더 배치의 `requirement_change_impact_report.json`을 연다.
- `Open output folder`: 선택한 결과 행의 output folder를 열고, 선택된 행이 없으면 마지막 변환의 output root를 연다.
- `Help`: 이 GUI 사용자 가이드를 연다.
- `Clear recent`: 저장된 최근 입력/출력 경로를 지운다.

## 8) 최근 경로 저장

GUI는 반복 사용성을 위해 최근 입력 PDF, 입력 폴더, output folder를 local-only JSON state로 저장한다.

- 저장 대상은 경로 목록뿐이다.
- previous corpus manifest path는 profile이나 recent state에 저장하지 않는다.
- 원문 텍스트, 표 내용, 이미지 내용, warning message는 저장하지 않는다.
- 시작 시 아직 존재하는 최근 경로만 보수적으로 입력칸에 복구한다.
- 공유 PC나 민감한 경로가 노출될 수 있는 환경에서는 `Clear recent`를 누른다.

## 9) 문제 진단

### GUI가 열리지 않음

- Python 3.11 이상인지 확인한다.
- Tkinter가 포함된 Python 설치본인지 확인한다.
- 아래 명령이 창 없이 도움말을 출력하는지 확인한다.

```bash
python -m pdf2md.gui --help
```

- 아래 doctor 명령의 `error`는 먼저 조치하고, `advisory`는 OCR 또는 desktop window probe처럼 선택 기능/환경 의존 항목으로 해석한다.

```bash
python -m pdf2md.gui --doctor
```

### `pdf2md-gui` 명령이 안 잡힘

가상환경을 활성화한 뒤 editable install을 다시 실행한다.

```bash
python -m pip install -e .[dev]
python -m pdf2md.gui
```

### output folder 오류

- output path가 파일이면 폴더 경로로 바꾼다.
- 쓰기 권한이 있는 사용자 폴더를 선택한다.
- 회사 보안 정책으로 Desktop/Documents 접근이 제한되면 별도 작업 폴더를 만든다.

### OCR warning

OCR을 사용하려면 Tesseract가 설치되어 있어야 한다.

```bash
tesseract --version
```

OCR이 필요 없으면 `Force OCR`을 끄고 다시 실행한다.

### 표나 이미지 결과가 기대와 다름

- 표는 안전한 경우에만 Markdown table로 출력된다.
- 복잡하거나 애매한 표는 HTML fallback이 우선된다.
- 이미지는 기본적으로 referenced mode로 별도 파일에 저장된다.
- 자세한 fallback 이유는 `report.json`의 warning과 summary를 확인한다.

## 10) Smoke evidence

GUI 변경을 반복 확인할 때는 Tk window를 띄우지 않는 local-only smoke evidence runner를 먼저 실행한다.

```bash
python scripts/run_gui_smoke_evidence.py --output-dir /tmp/pdf2md-gui-smoke --state-path /tmp/pdf2md-gui-smoke/gui_state.json
```

자동화 로그에는 JSON만 출력할 수 있다.

```bash
python scripts/run_gui_smoke_evidence.py --output-dir /tmp/pdf2md-gui-smoke --state-path /tmp/pdf2md-gui-smoke/gui_state.json --json-only
```

생성되는 `gui_smoke_evidence.json`은 public output schema가 아니라 로컬 검증 artifact다. 포함 대상은 GUI runtime doctor diagnostics, `python -m pdf2md.gui --help` 결과, preset별 runner smoke status, isolated GUI state round-trip, 산출물 존재 여부, 수동 checklist 상태다.

evidence에는 원문 PDF 텍스트, 표 내용, 이미지 내용, 변환 warning message, workspace/home absolute path를 저장하지 않는다. 실제 Tk window에서 한국어 기본 UI, English 전환, preset lock/unlock, batch percent, 단일 page-level percent와 완료 `100%`, local-only state 복구/clear는 macOS/Windows checklist에 따라 사람이 확인한다.

## 11) Support bundle

문제 보고를 위해 공유 가능한 자료가 필요하면 sanitized support bundle을 만든다.

```bash
python scripts/create_gui_support_bundle.py --output-dir /tmp/pdf2md-gui-support --smoke-evidence /tmp/pdf2md-gui-smoke/gui_smoke_evidence.json
```

생성 파일:

- `gui_support_bundle.json`
- `gui_support_bundle.md`

support bundle은 public output schema가 아니라 local-only 지원 artifact다. 포함 대상은 status count, warning code/count, sanitized artifact label, environment/runtime code, smoke failed check code다. 원문 PDF 텍스트, Markdown 본문, 표 내용, 이미지 내용, 변환 warning message, home/workspace absolute path는 저장하지 않는다.

릴리스 전에는 optional GUI release gate로 같은 headless 흐름을 한 번에 확인할 수 있다.

```bash
python scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-gui --gates gui
```

이 gate는 `python -m pdf2md.gui --help`, `python -m pdf2md.gui --doctor --doctor-format json`, smoke evidence runner, support bundle 생성기를 순차 실행하고 `release_gate_report.json`에 command/status/report path를 기록한다. smoke evidence 또는 support bundle redaction 검증이 실패하면 release gate도 실패한다.

wheel 설치 환경에서는 source checkout의 `docs/GUI_USER_GUIDE.md`가 없을 수 있으므로 GUI help는 packaged `pdf2md.resources/GUI_USER_GUIDE.md` fallback을 사용한다. packaging release gate는 `wheel_contract_report.json`으로 GUI module, support/profile helper, packaged help resource, `pdf2md-gui` console script metadata 포함 여부를 검사한다.

CLI와 GUI headless runner가 같은 산출물을 만드는지도 release 전에 확인할 수 있다.

```bash
python scripts/run_gui_cli_parity.py --output-dir /tmp/pdf2md-gui-cli-parity
python scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-gui-parity --gates gui-parity
```

`gui_cli_parity_report.json`은 synthetic PDF fixture의 raw 본문을 저장하지 않고, Markdown, manifest, report, RAG sidecar별 normalized hash match 결과와 mismatch summary만 저장하는 local-only 검증 artifact다.

CLI와 GUI headless runner의 성능 차이는 local-only benchmark로 확인한다.

```bash
python scripts/benchmark_gui_cli_parity.py --output-dir /tmp/pdf2md-gui-cli-benchmark
python scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-gui-benchmark --gates gui-benchmark
```

`gui_cli_benchmark_report.json`은 elapsed ms, pages/sec, GUI duration ratio, output hash equality, optional threshold/advisory policy 결과를 저장한다. 기본 threshold는 advisory이며, 명시 threshold와 fail 옵션이 함께 있을 때만 성능 회귀를 실패로 처리한다.

## 12) Preset 비교 scorecard

`RAG 등록용(최적화)`와 `기술 스펙 RAG`의 산출물 차이를 반복 비교하려면 GUI를 직접 누르는 대신 같은 preset matrix를 쓰는 local-only runner를 실행한다.

```bash
python scripts/run_preset_eval.py --input-pdf spec.pdf --output-root /tmp/pdf2md-preset-eval --presets rag_optimized,technical_spec_rag --domain-adapter nvme
```

생성되는 `preset_eval_report.json`, `preset_artifact_comparison.json`, `preset_scorecard.md`는 score, gate condition, artifact 존재/크기/record count, warning/code count만 저장한다. 원문 PDF 텍스트, 표 본문, 이미지 내용은 비교 report에 복사하지 않는다.

릴리스 전 자동 점검에 포함하려면:

```bash
python scripts/run_release_gates.py --output-dir /tmp/pdf2md-release-preset --gates preset-eval --preset-eval-input-pdf spec.pdf --preset-eval-domain-adapter nvme --preset-eval-min-score 80
```

## 13) 배포 방식 메모

현재 비개발자 기본 경로는 source/ZIP + venv setup + `python -m pdf2md.gui` 실행이다.

PyInstaller/native bundle은 Tkinter, PyMuPDF, Tesseract, code signing/notarization smoke가 운영체제별로 정리되기 전까지 공식 기본 배포 경로로 보지 않는다.
