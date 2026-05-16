# macOS GUI 빠른 시작 가이드

이 문서는 CLI가 익숙하지 않은 사용자가 macOS에서 `pdf2md` GUI를 실행해 PDF 파일 또는 폴더를 변환하는 최소 절차를 정리한다.

자동화, CI, 반복 배치 변환은 GUI보다 `python3 -m pdf2md` CLI를 권장한다.

GUI 화면별 사용법은 별도 문서 `docs/GUI_USER_GUIDE.md`에서 확인한다. GUI의 `Help` 버튼도 같은 문서를 연다.

## 1) 준비물

- macOS
- Python 3.11 이상
- PDF 파일 또는 PDF가 들어 있는 폴더
- OCR을 사용할 경우 Tesseract

Python 버전 확인:

```bash
python3 --version
```

권장 출력 예시:

```text
Python 3.11.x
```

Homebrew를 사용하는 경우:

```bash
brew install python@3.11
```

OCR을 사용할 경우:

```bash
brew install tesseract
tesseract --version
```

## 2) 프로젝트 폴더 준비

Git을 사용할 수 있으면:

```bash
git clone https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex.git
cd ConvertPdfToMarkdownWithCodex
```

Git을 쓰지 않는 경우에는 소스 ZIP을 받은 뒤 압축을 풀고 해당 폴더로 이동한다.

## 3) 가상환경 만들기

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

`python3.11` 명령이 없다면 `python3 -m venv .venv311`을 사용하되, `python3 --version`이 3.11 이상인지 먼저 확인한다.

## 4) GUI 실행

module 실행:

```bash
python -m pdf2md.gui
```

entry point 실행:

```bash
pdf2md-gui
```

`pdf2md-gui`가 잡히지 않으면 같은 가상환경에서 아래를 다시 실행한다.

```bash
python -m pip install -e .[dev]
```

GUI 도움말 smoke:

```bash
python -m pdf2md.gui --help
```

이 명령은 창을 띄우지 않고 도움말만 출력해야 한다.

## 5) 단일 PDF 변환

1. `PDF file`을 선택한다.
2. `Browse`로 PDF 파일을 선택한다.
3. 필요하면 `Output folder`를 선택한다.
4. `Start conversion`을 누른다.
5. 완료 후 Results 표에서 `Status`, `Warnings`, `Markdown`, `Report` 경로를 확인한다.

출력 폴더를 지정하지 않으면 입력 PDF 옆에 `<pdf_stem>_output` 폴더가 생성된다.

## 6) 폴더 배치 변환

1. `PDF folder`를 선택한다.
2. PDF가 들어 있는 폴더를 선택한다.
3. 필요하면 `Skip existing`을 켠다.
4. `Start conversion`을 누른다.
5. 진행 중 중단하려면 `Cancel`을 누른다.

취소는 문서 경계에서 처리된다. 이미 완료된 문서의 산출물은 삭제하지 않고, 아직 시작하지 않은 문서는 `cancelled` 상태로 표시된다.

## 7) 결과 확인

GUI 완료 후 Results 표에서 아래를 확인한다.

- `Status`: `success`, `partial_success`, `failed`, `skipped`, `cancelled`
- `Warnings`: warning count와 warning code
- `Markdown`: 생성된 Markdown 경로
- `Report`: `report.json` 경로
- `Retry`: 실패 문서가 재시도 후보인지 여부

원문 텍스트, 표, 이미지 내용은 GUI summary에서 요약하지 않는다. 자세한 품질 판단은 `report.json`과 `manifest.json`을 확인한다.

GUI 화면에서 바로 설명이 필요하면 `Help` 버튼을 누른다.

선택한 Results 행에서 `Open Markdown`, `Open Report`, `Open Manifest`, `Open Assets`, `Open output folder`로 산출물을 바로 열 수 있다. GUI는 최근 입력 파일/폴더와 output folder를 local-only state로 저장하며, `Clear recent`로 지울 수 있다.

## 8) 로컬 GUI smoke checklist

1. `python -m pdf2md.gui --help`가 창 없이 종료되는지 확인한다.
2. `python -m pdf2md.gui`로 GUI 창을 연다.
3. 단일 PDF를 변환하고 Results 표에서 Markdown/report/manifest 경로를 확인한다.
4. 선택한 결과 행의 Markdown/report/manifest/assets 또는 output folder가 열리는지 확인한다.
5. 기본 한국어 UI에서 `English`로 바꿨을 때 주요 label/button/status가 영어로 바뀌는지 확인한다.
6. `기본 모드(원본 유지)`, `RAG 등록용(최적화)`, `Optimize Options(유저 선택)` preset 변경 시 세부 옵션 잠금/해제가 맞는지 확인한다.
7. 폴더 배치 변환에서 문서 index/total과 percent text가 함께 움직이는지 확인한다.
8. 단일 PDF 변환은 처리 중 percent를 추정하지 않고 완료 시 `100%`만 표시하는지 확인한다.
9. `Cancel`을 눌렀을 때 현재 문서 완료 후 남은 문서가 `cancelled`로 표시되는지 확인한다.
10. GUI를 닫고 다시 열었을 때 최근 경로, 언어, preset이 복구되는지 확인한다.
11. `Clear recent` 후 재실행하면 최근 경로가 복구되지 않는지 확인한다.

## 9) 배포 방식 판단

현재 macOS 비개발자 기본 경로는 source/ZIP + venv setup + `python -m pdf2md.gui` 실행이다.

PyInstaller/native bundle은 Tkinter, PyMuPDF, Tesseract 포함/진단, code signing/notarization smoke가 정리되기 전까지 공식 기본 배포 경로로 보지 않는다.

## 10) 문제 진단

### Python 버전 오류

- `python --version` 또는 `python3 --version`이 3.11 이상인지 확인한다.
- 가상환경을 다시 활성화한다.

```bash
source .venv311/bin/activate
```

### Tkinter 오류

- Python 설치본에 Tcl/Tk 지원이 빠졌을 수 있다.
- Homebrew 또는 python.org Python을 다시 설치한 뒤 가상환경을 다시 만든다.

### `pdf2md-gui` 명령이 안 잡힘

```bash
source .venv311/bin/activate
python -m pip install -e .[dev]
python -m pdf2md.gui
```

### output folder 권한 오류

- Desktop, Documents, Downloads 같은 사용자 쓰기 가능 폴더를 선택한다.
- 이미 같은 이름의 파일이 output folder 경로에 있으면 폴더로 바꾸거나 다른 경로를 선택한다.

### OCR warning

```bash
tesseract --version
```

Tesseract가 없으면 OCR warning이 발생할 수 있다. OCR이 필요 없으면 `Force OCR`을 끈 상태로 실행한다.
