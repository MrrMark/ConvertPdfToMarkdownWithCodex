# Windows A-Z 설치/실행 가이드 (Python 3.11 기준)

이 문서는 **Windows 환경에서 `pdf2md`를 설치하고 실행하는 전체 절차**를 다룹니다.
대상: 처음 세팅하는 사용자

---

## 1) 사전 준비

필수:
- Windows 10/11
- PowerShell (권장)
- Git
- Python 3.11.x

선택(권장):
- Tesseract OCR (OCR 기능 사용 시 필수)

---

## 2) Git 설치

1. [Git for Windows](https://git-scm.com/download/win) 설치
2. 설치 후 PowerShell에서 확인

```powershell
git --version
```

### 2-1) 회사 보안 환경: 온라인 설치가 막힌 경우

사내 보안 정책으로 인해 인터넷에서 직접 설치가 불가능하면 아래 방식으로 진행하세요.

#### 방법 A. 오프라인 설치 파일 반입

1. 인터넷 가능한 PC에서 Git for Windows 설치 파일(`.exe`) 다운로드  
2. 회사 정책에 맞는 반입 경로(내부 파일 반입 승인, 사내 저장소 등)로 파일 이동  
3. 대상 PC에서 설치 실행  
4. 설치 후 확인

```powershell
git --version
```

#### 방법 B. Portable Git(무설치) 사용

설치 권한(관리자 권한)이 제한된 경우, Portable Git(`PortableGit-*.7z.exe`)를 사용할 수 있습니다.

1. 인터넷 가능한 PC에서 Git for Windows Releases의 Portable 파일 다운로드  
2. 사내 승인 경로로 대상 PC에 반입  
3. 원하는 경로에 압축 해제 (예: `C:\Tools\PortableGit`)  
4. 현재 세션 PATH에 추가

```powershell
$env:Path = "C:\Tools\PortableGit\cmd;$env:Path"
git --version
```

5. 영구 적용(선택): 시스템 정책 허용 시 사용자 환경변수 PATH에 `C:\Tools\PortableGit\cmd` 추가

#### 보안 검증(권장)

반입한 설치 파일 무결성 검증:

```powershell
Get-FileHash .\Git-Installer.exe -Algorithm SHA256
```

공식 배포 페이지의 체크섬과 비교 후 설치하세요.

---

## 3) Python 3.11 설치

1. [Python 3.11 다운로드](https://www.python.org/downloads/windows/)
2. 설치 시 반드시 `Add python.exe to PATH` 체크
3. 설치 확인

```powershell
python --version
pip --version
```

권장 출력 예시:
- `Python 3.11.x`

---

## 4) 저장소 클론

```powershell
git clone https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex.git
cd ConvertPdfToMarkdownWithCodex
```

### 4-1) 회사 보안 환경: `git clone`이 막힌 경우

사내 정책으로 `git clone`이 불가능해도 실행할 수 있습니다.

대체 경로:

1. 소스 ZIP 반입  
- 인터넷 가능한 PC에서 저장소 ZIP 다운로드  
- 사내 승인된 반입 채널(내부 파일서버, 승인 USB 등)로 전달  
- 대상 PC에서 압축 해제

2. 사내 미러/아티팩트 저장소 사용  
- Nexus/Artifactory/내부 Git 미러에서 소스 패키지 다운로드  

3. 릴리스 번들 사용(권장)  
- 소스 ZIP + 의존성 wheel 묶음(`wheelhouse`) + 설치 스크립트 반입

압축 해제 후 작업 폴더로 이동:

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
```

---

## 5) 가상환경 생성/활성화

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

PowerShell 실행 정책 오류가 나면(최초 1회):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

다시 활성화:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## 6) 의존성 설치

```powershell
python -m pip install --upgrade pip
pip install -e .[dev]
```

설치 확인:

```powershell
python -m pdf2md --help
```

---

## 7) 기본 실행

예시 입력 파일: `sample.pdf`

```powershell
python -m pdf2md .\sample.pdf -o .\output
```

생성 파일:
- `output\document.md`
- `output\manifest.json`
- `output\report.json`

최근 버전 기준 추가 확인 포인트:
- `manifest.json > schema_version`
- `manifest.json > images[].alt_text`
- `manifest.json > images[].caption_text`, `caption_source` (인접 캡션이 확실한 경우만)
- `report.json > schema_version`
- `report.json > page_results[].status`
- `report.json > summary.page_status_counts`
- `report.json > summary.table_fallback_count`
- `report.json > summary.table_fallbacks`
- `report.json > summary.table_mode_requested`
- `report.json > summary.table_markdown_forced_count`
- `report.json > summary.table_html_forced_count`

`report.json`에서 특히 확인할 항목:
- `summary.table_quality`: 표별 품질 메타데이터
- `summary.table_total`, `table_gfm_count`, `table_html_count`
- `summary.table_recovered_count`, `table_unresolved_count`

---

## 8) 자주 쓰는 옵션

페이지 범위:

```powershell
python -m pdf2md .\sample.pdf -o .\output --pages 1-3,5
```

페이지 마커 유지:

```powershell
python -m pdf2md .\sample.pdf -o .\output --keep-page-markers
```

페이지 마커 제거:

```powershell
python -m pdf2md .\sample.pdf -o .\output --no-page-markers
```

이미지 모드:

```powershell
python -m pdf2md .\sample.pdf -o .\output --image-mode referenced
```

표 모드:

```powershell
python -m pdf2md .\sample.pdf -o .\output --table-mode auto
```

HTML 표 강제:

```powershell
python -m pdf2md .\sample.pdf -o .\output --table-mode html
```

Markdown 표 강제:

```powershell
python -m pdf2md .\sample.pdf -o .\output --table-mode markdown
```

운영 권장:

- 일반 RAG / AI Code Assistant 기본값: `--table-mode auto`
- 토큰 효율 최우선: `--table-mode markdown`
- 복잡 표 구조 보존 최우선: `--table-mode html`

문서 유형별 추천:

- 기술 스펙 / 프로토콜 문서: `auto` 또는 `html`
- 본문 중심 문서: `markdown`
- 표 구조 정확도가 중요한 검색 인덱스: `html`

강제 OCR:

```powershell
python -m pdf2md .\sample.pdf -o .\output --force-ocr
```

로그를 자세히 보기:

```powershell
python -m pdf2md .\sample.pdf -o .\output --verbose
python -m pdf2md .\sample.pdf -o .\output --debug
```

---

## 9) OCR 사용 (Windows)

`--force-ocr` 또는 텍스트 없는 페이지 OCR을 사용하려면 Tesseract가 필요합니다.

1. Windows용 Tesseract 설치
- 일반적으로 [UB Mannheim 빌드](https://github.com/UB-Mannheim/tesseract/wiki) 사용

2. 설치 경로를 PATH에 추가
- 예: `C:\Program Files\Tesseract-OCR`

3. 확인

```powershell
tesseract --version
```

정상 출력되면 OCR 기능 사용 가능

---

## 10) 테스트 실행

```powershell
pytest -q -p no:cacheprovider
```

또는

```powershell
python -m pytest -q -p no:cacheprovider
```

---

## 11) 종료 코드 의미

- `0`: 성공
- `1`: 치명적 실패
- `2`: 부분 성공 (일부 요소 warning/fallback 포함)

`2`는 실패가 아니라, 부분 fallback이 포함된 정상적인 실행일 수 있습니다.
최근 버전에서는 표 복구/보수 fallback 정책 때문에 `2`가 자주 나올 수 있으며, 이때는 `report.json`의
`warnings`, `summary.table_quality`, `summary.table_fallback_count`,
`summary.table_fallbacks`, `summary.page_status_counts`를 함께 확인하세요.

---

## 12) 트러블슈팅

### A. `python` 명령이 안 잡힘
- Python 설치 시 PATH 체크 누락 가능
- 새 PowerShell 재실행
- `py -3.11 --version`으로 확인

### B. `ModuleNotFoundError`
- 가상환경 미활성화 가능
- 아래 순서 재실행

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

### C. OCR warning (`OCR_RUNTIME_UNAVAILABLE`)
- Tesseract 미설치 또는 PATH 미설정
- `tesseract --version` 먼저 확인

### D. 이미지가 없다는 warning (`IMAGE_NOT_FOUND`)
- PDF에 embedded 이미지가 없으면 정상 경고일 수 있음
- 스캔 PDF라도 이미지 객체가 표준 임베드 형식이 아닐 수 있음

### E. `embedded` 또는 `placeholder` 모드인데 `assets\images`가 비어 있음
- 최근 동작에서는 정상입니다.
- `referenced` 모드에서만 실제 이미지 파일을 저장합니다.
- `embedded`는 Markdown 내부 data URI, `placeholder`는 comment만 남깁니다.

### F. 표가 기대보다 많거나 적게 추출됨
- 최신 로직은 표 후보를 다중 전략으로 탐색하고 보수적으로 복구합니다.
- `markdown` 모드에서는 복잡 표도 Markdown으로 강제되므로 일부 구조 손실이 있을 수 있습니다.
- 아래를 우선 확인하세요:
  - `report.json > summary.table_total`
  - `report.json > summary.table_recovered_count`
  - `report.json > summary.table_unresolved_count`
  - `report.json > summary.table_fallback_count`
  - `report.json > summary.table_fallbacks`
  - `report.json > summary.table_mode_requested`
  - `report.json > summary.table_markdown_forced_count`
  - `report.json > summary.table_html_forced_count`
  - `report.json > warnings[].details.reasons`
- `AMBIGUOUS_GRID`, `LOW_DATA_DENSITY` 경고가 많은 문서는 원본 PDF 구조가 불명확한 경우가 많습니다.

### G. 권한 문제
- 회사 보안 정책으로 스크립트 실행 제한 가능
- PowerShell 정책 또는 보안 솔루션 정책 확인

---

## 13) 업데이트 방법

```powershell
git pull origin main
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

---

## 14) 권장 실행 예시 (복사해서 바로 실행)

```powershell
git clone https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex.git
cd ConvertPdfToMarkdownWithCodex
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
python -m pdf2md .\sample.pdf -o .\output --pages 1-3 --keep-page-markers --image-mode referenced --table-mode auto
```

---

## 15) `git clone` 없이 실행하는 실전 예시

### A. 소스 ZIP만 있는 경우(인터넷 가능 환경)

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
python -m pdf2md .\sample.pdf -o .\output
```

### B. 완전 오프라인 환경(의존성 wheel 반입)

사전 준비(인터넷 가능한 환경):
- 프로젝트 소스 ZIP
- `wheelhouse` 폴더(필요 패키지 wheel 파일 모음)

사내 PC 실행:

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --no-index --find-links .\wheelhouse -e .
python -m pdf2md .\sample.pdf -o .\output
```

### C. OCR까지 필요한 경우

- `tesseract.exe`가 설치되어 있거나 PATH에 잡혀 있어야 합니다.
- 보안 환경에서는 Portable/오프라인 설치 방식으로 반입 후 아래 확인:

```powershell
tesseract --version
```
