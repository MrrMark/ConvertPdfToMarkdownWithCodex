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

자동화에서 읽기 쉬운 JSON이 필요하면:

```bash
python -m pdf2md.gui --doctor --doctor-format json
```

운영체제별 설치/실행 준비는 다음 문서를 참고한다.

- macOS: `docs/MACOS_GUI_QUICKSTART.md`
- Windows: `docs/WINDOWS_A_TO_Z_GUIDE.md`

## 2) 화면 구성

### Language

- 기본 언어는 한국어다.
- `English`를 선택하면 주요 label, button, status 문구가 영어로 바뀐다.
- 언어 선택은 local-only JSON state에 저장되며 변환 산출물에는 영향을 주지 않는다.

### Preset

- `기본 모드(원본 유지)`: 원문 보존을 우선하는 보수적 기본값이다.
- `RAG 등록용(최적화)`: Markdown 원문을 임의로 바꾸지 않고 RAG table sidecar, page marker, header/footer 보정, hyphenation 보정 같은 RAG 친화 옵션을 켠다.
- `Optimize Options(유저 선택)`: image/table/RAG/domain과 상세 flag를 직접 고른다.
- `Pages`, `Password`, `OCR lang`, 입력/출력 경로는 preset을 바꿔도 유지된다.
- `custom`이 아닌 preset에서는 세부 변환 옵션이 읽기 전용으로 표시된다.

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
- `Domain`: NVMe, PCIe, OCP, TCG, customer requirements 같은 도메인 adapter 선택이다.

### Flags

- `Skip existing`: 배치 변환에서 기존 Markdown, manifest, report가 있으면 건너뛴다.
- `Confidential safe`: 공개 공유용 metadata에서 민감한 경로/파일명 노출을 줄인다.
- `Force OCR`: 텍스트 layer가 있어도 OCR을 강제로 시도한다.
- `Page markers`: Markdown에 page marker를 남긴다.
- `Remove header/footer`: 반복 header/footer를 보수적으로 제거한다.
- `Dedupe images`: 같은 이미지 객체를 중복 저장하지 않는다.
- `Repair hyphenation`: 명확한 줄바꿈 hyphenation을 복구한다.
- `Figure crop fallback`: caption이 있는 figure에 embedded image가 없을 때 page crop fallback을 시도한다.

### Progress

- 단일 PDF 변환은 처리 중임을 나타내는 indeterminate progress로 표시된다.
- 폴더 배치 변환은 현재 문서 index/total과 percent text를 함께 표시한다. 예: `2/10 (20%)`
- page-level 진행률 callback이 없으므로 실제 page 처리율처럼 보이는 임의 진행률은 표시하지 않는다.
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

## 4) 폴더 배치 변환

1. `PDF folder`를 선택한다.
2. PDF 파일들이 들어 있는 폴더를 선택한다.
3. 이미 변환된 문서를 건너뛰려면 `Optimize Options(유저 선택)`에서 `Skip existing`을 켠다.
4. `Start conversion`을 누른다.
5. 중간에 멈추려면 `Cancel`을 누른다.

취소는 문서 경계에서 처리된다. 현재 처리 중인 PDF는 가능한 한 끝까지 처리하고, 아직 시작하지 않은 PDF는 `cancelled` 상태로 기록한다.

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

상세 품질 판단은 `report.json`과 `manifest.json`에서 확인한다. GUI summary는 원문 텍스트, 표, 이미지 내용을 요약하거나 재서술하지 않는다.

결과 행을 선택하면 `Open Markdown`, `Open Report`, `Open Manifest`, `Open Assets`, `Open output folder`로 해당 산출물을 바로 열 수 있다. 경로가 없거나 OS가 열 수 없는 경우에는 변환 실패가 아니라 GUI warning/log로만 표시된다.

## 6) Status 의미

- `success`: 변환이 정상 완료됐다.
- `partial_success`: 변환은 완료됐지만 warning이나 fallback이 있다. `report.json`을 확인한다.
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
- `Open output folder`: 선택한 결과 행의 output folder를 열고, 선택된 행이 없으면 마지막 변환의 output root를 연다.
- `Help`: 이 GUI 사용자 가이드를 연다.
- `Clear recent`: 저장된 최근 입력/출력 경로를 지운다.

## 8) 최근 경로 저장

GUI는 반복 사용성을 위해 최근 입력 PDF, 입력 폴더, output folder를 local-only JSON state로 저장한다.

- 저장 대상은 경로 목록뿐이다.
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

evidence에는 원문 PDF 텍스트, 표 내용, 이미지 내용, 변환 warning message, workspace/home absolute path를 저장하지 않는다. 실제 Tk window에서 한국어 기본 UI, English 전환, preset lock/unlock, batch percent, 단일 완료 `100%`, local-only state 복구/clear는 macOS/Windows checklist에 따라 사람이 확인한다.

## 11) 배포 방식 메모

현재 비개발자 기본 경로는 source/ZIP + venv setup + `python -m pdf2md.gui` 실행이다.

PyInstaller/native bundle은 Tkinter, PyMuPDF, Tesseract, code signing/notarization smoke가 운영체제별로 정리되기 전까지 공식 기본 배포 경로로 보지 않는다.
