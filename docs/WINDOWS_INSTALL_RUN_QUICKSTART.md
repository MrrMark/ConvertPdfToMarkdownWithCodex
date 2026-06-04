# Windows 설치 및 실행 빠른 가이드

이 문서는 Windows 사용자가 `pdf2md`를 처음 받아서 **설치, CLI 실행, GUI 실행, 결과 확인**까지 진행하는 최소 절차를 정리한다.

상세 운영, 배치, 오프라인 설치, 릴리스 검증 절차는 `docs\WINDOWS_A_TO_Z_GUIDE.md`를 참고한다.

## 1) 준비물

필수:

- Windows 10 또는 Windows 11
- Python 3.11 이상
- 이 프로젝트 소스 폴더

권장:

- Python Launcher for Windows (`py` 명령)
- OCR을 사용할 경우 Tesseract OCR
- Git으로 업데이트할 경우 Git

Python 확인:

```powershell
py -3.11 --version
python --version
```

둘 중 하나가 `Python 3.11.x` 이상이면 진행할 수 있다. 프로젝트의 Windows setup script 기본값은 최신 검증축인 `Python 3.14`와 `.venv314`를 사용한다.

## 2) 프로젝트 받기

ZIP으로 받은 경우:

1. ZIP 파일을 압축 해제한다.
2. PowerShell을 열고 프로젝트 폴더로 이동한다.

```powershell
cd C:\Work\ConvertPdfToMarkdown
```

Git을 사용할 수 있는 경우:

```powershell
git clone https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex.git
cd ConvertPdfToMarkdownWithCodex
```

회사 보안 정책으로 Git이 막혀 있으면 ZIP 배포본을 사용한다.

## 3) 자동 설치

프로젝트 폴더에서 아래 명령을 실행한다.

```powershell
.\scripts\setup_windows_env.bat
```

이 명령은 다음을 수행한다.

- Python 실행기 확인
- `.venv314` 가상환경 생성 또는 재사용
- `pip` 업그레이드
- 프로젝트와 개발/검증 의존성 설치
- `python -m pdf2md --help` smoke 확인

PowerShell 실행 정책 오류가 나면 현재 사용자 범위에서만 정책을 완화한 뒤 다시 실행한다.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\scripts\setup_windows_env.bat
```

Python 3.11로 명시 설치하고 싶으면 PowerShell script를 직접 실행한다.

```powershell
.\scripts\setup_windows_env.ps1 -PythonVersion 3.11 -VenvDir .venv311 -SkipWingetInstall
```

## 4) 수동 설치

자동 설치가 막힌 환경에서는 아래 순서로 진행한다.

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pdf2md --help
```

CMD를 사용하는 경우 활성화 명령만 다르다.

```bat
.\.venv311\Scripts\activate.bat
```

## 5) CLI로 단일 PDF 변환

가상환경을 활성화한 상태에서 실행한다.

```powershell
python -m pdf2md .\sample.pdf
```

출력 폴더를 직접 지정하려면:

```powershell
python -m pdf2md .\sample.pdf -o .\output
```

자주 쓰는 옵션:

```powershell
python -m pdf2md .\sample.pdf -o .\output --pages 1-3,5
python -m pdf2md .\sample.pdf -o .\output --password secret
python -m pdf2md .\sample.pdf -o .\output --force-ocr --ocr-lang kor+eng
python -m pdf2md .\sample.pdf -o .\output --rag-profile technical_spec_rag --domain-adapter nvme
```

이미지 파일을 팀 RAG에 업로드할 수 없는 환경에서는 CLI에서 GUI 프리셋과 같은 조합을 아래처럼 실행한다.

```powershell
python -m pdf2md .\sample.pdf -o .\output --rag-profile technical_spec_rag --image-mode placeholder --rag-figure-text-chunks
```

이 조합은 PNG/JPG 파일을 생성하지 않고, `document.md`에는 deterministic placeholder comment를 남긴다. 그림 주변의 관측 텍스트는 `figures_rag.jsonl`과 `retrieval_chunks_rag.jsonl`의 `figure_text` chunk로 보존한다.

## 6) CLI로 폴더 배치 변환

폴더 바로 아래 PDF를 한 번에 변환한다.

```powershell
python -m pdf2md --input-dir .\pdfs
```

Windows helper script를 쓰면 환경이 없을 때 setup을 먼저 시도하고 배치 변환을 실행한다.

```powershell
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

기존 산출물이 있는 문서를 건너뛰려면:

```powershell
python -m pdf2md --input-dir .\pdfs --skip-existing
```

배치 결과는 기본적으로 입력 폴더 아래 `output\`에 생성된다.

## 7) GUI 실행

CLI가 익숙하지 않은 사용자는 GUI를 실행한다.

자동 설치를 사용했다면:

```powershell
.\.venv314\Scripts\Activate.ps1
python -m pdf2md.gui
```

수동으로 `.venv311`을 만들었다면:

```powershell
.\.venv311\Scripts\Activate.ps1
python -m pdf2md.gui
```

entry point가 잡혀 있으면 아래 명령도 사용할 수 있다.

```powershell
pdf2md-gui
```

GUI가 열리기 전에 환경만 확인하려면:

```powershell
python -m pdf2md.gui --help
python -m pdf2md.gui --doctor
```

GUI 기본 사용 순서:

1. `PDF file` 또는 `PDF folder`를 선택한다.
2. `Browse`로 입력 PDF 또는 폴더를 선택한다.
3. 필요하면 `Output folder`를 선택한다.
4. 목적에 맞는 preset을 선택한다.
5. `Start conversion`을 누른다.
6. 완료 후 Results 표에서 `Status`, `Warnings`, `Markdown`, `Report`를 확인한다.

추천 preset:

| 목적 | GUI preset |
|---|---|
| 원문 보존 중심 기본 변환 | `기본 모드(원본 유지)` |
| 일반 RAG 등록 | `RAG 등록용(최적화)` |
| NVMe/PCIe 등 기술 스펙 RAG | `기술 스펙 RAG` |
| PNG/JPG 업로드 불가 팀 RAG | `이미지 업로드 불가 RAG 대응` |
| 공유용 metadata 민감정보 최소화 | `민감정보 보호 RAG` |
| 세부 옵션 직접 제어 | `Optimize Options(유저 선택)` |

`이미지 업로드 불가 RAG 대응` preset은 내부적으로 `technical_spec_rag`, `image_mode=placeholder`, `rag_figure_text_chunks=true`를 사용한다. `Domain=manual`을 선택하면 고객 requirement용 label과 keyword를 직접 입력할 수 있다.

## 8) 결과 확인

단일 PDF 출력 예:

```text
output\
  document.md
  manifest.json
  report.json
  text_blocks_rag.jsonl
  semantic_units_rag.jsonl
  requirements_rag.jsonl
  cross_refs_rag.jsonl
  requirement_traceability_rag.jsonl
  technical_tables_rag.jsonl
  retrieval_chunks_rag.jsonl
  figures_rag.jsonl
  assets\
    images\
```

확인 우선순위:

- `document.md`: Markdown 본문
- `manifest.json`: 입력/옵션/asset/RAG sidecar metadata
- `report.json`: 페이지별 상태, warning, stage duration, pages/sec
- `retrieval_chunks_rag.jsonl`: RAG 등록용 chunk
- `figures_rag.jsonl`: 그림/이미지 provenance
- `tables_rag.jsonl`, `rag_tables.md`: `--rag-table-output both` 또는 관련 preset 사용 시 생성

종료 코드:

- `0`: 성공
- `1`: 치명적 실패
- `2`: 부분 성공. 일부 warning 또는 fallback이 있었지만 산출물이 생성된 상태일 수 있다.

## 9) OCR 설정

OCR이 필요한 PDF라면 Tesseract를 설치하고 PATH에 추가한다.

확인:

```powershell
tesseract --version
python scripts\check_ocr_runtime.py --ocr-lang eng
```

한글 OCR이 필요하면 Tesseract 언어 데이터가 설치되어 있어야 한다.

```powershell
python scripts\check_ocr_runtime.py --ocr-lang kor+eng
python -m pdf2md .\sample.pdf -o .\output --force-ocr --ocr-lang kor+eng
```

OCR이 필요 없는 디지털 PDF에서는 `--force-ocr`를 켜지 않는 것이 기본 권장이다.

## 10) 자주 나는 문제

### `python` 또는 `py` 명령이 안 잡힘

- Python 설치 시 `Add python.exe to PATH`를 체크했는지 확인한다.
- 새 PowerShell을 연다.
- `py -3.11 --version` 또는 `py -3.14 --version`을 확인한다.

### PowerShell script 실행이 막힘

현재 사용자 범위에서만 실행 정책을 조정한다.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

그래도 막히면 `.bat` wrapper를 사용한다.

```powershell
.\scripts\setup_windows_env.bat
```

### `ModuleNotFoundError`

가상환경이 비활성화됐거나 의존성 설치가 빠진 상태일 수 있다.

```powershell
.\.venv314\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### GUI가 열리지 않음

먼저 창 없는 smoke를 확인한다.

```powershell
python -m pdf2md.gui --help
python -m pdf2md.gui --doctor
```

`pdf2md-gui`가 안 잡혀도 `python -m pdf2md.gui`가 동작하면 GUI 실행은 가능하다.

### 출력 폴더 권한 오류

- Desktop, Documents, Downloads 같은 사용자 쓰기 가능 폴더를 선택한다.
- 회사 보안 정책으로 막히면 `C:\Work\pdf2md-output` 같은 별도 작업 폴더를 만든다.
- output path가 파일이면 폴더 경로로 바꾼다.

### 이미지가 파일로 안 생김

- `image_mode=placeholder`에서는 정상이다. PNG/JPG 파일을 만들지 않는다.
- `image_mode=referenced`에서만 `assets\images\*.png` 파일을 저장한다.

## 11) 업데이트

Git 사용 시:

```powershell
git pull origin main
.\.venv314\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

ZIP 배포본 사용 시:

1. 새 ZIP을 압축 해제한다.
2. 기존 PDF와 output 폴더를 새 소스 폴더 밖에 보관한다.
3. `.\scripts\setup_windows_env.bat`을 다시 실행한다.
