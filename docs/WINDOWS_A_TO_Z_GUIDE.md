# Windows A-Z 설치/실행 가이드 (Python 3.14 기준)

이 문서는 **Windows 환경에서 `pdf2md`를 설치하고 실행하는 전체 절차**를 다룹니다.
대상: 처음 세팅하는 사용자

---

## 1) 사전 준비

필수:
- Windows 10/11
- PowerShell (권장)
- Git
- Python 3.14.x

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

## 0) 원클릭 빠른 시작

ZIP 배포본을 압축 해제한 뒤, 아래 두 스크립트 중 하나로 바로 시작할 수 있습니다.

환경만 먼저 준비:

```powershell
.\scripts\setup_windows_env.bat
```

폴더 내 PDF 일괄 순차 변환까지 바로 실행:

```powershell
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

PowerShell 스크립트 본체:

- `scripts\setup_windows_env.ps1`
- `scripts\run_batch_folder_windows.ps1`

기본 정책:

- 최신 안정화 검증축 `Python 3.14`를 기본 사용
- 기본 가상환경 경로는 `.venv314`
- 배치 모드는 지정 폴더 바로 아래 PDF만 처리
- 결과는 입력 폴더 내부 `output\` 아래에 생성

---

## 3) Python 3.14 설치

1. [Python 3.14 다운로드](https://www.python.org/downloads/windows/)
2. 설치 시 반드시 `Add python.exe to PATH` 체크
3. 설치 확인

```powershell
python --version
pip --version
```

권장 출력 예시:
- `Python 3.14.x`

버전 정책:

- 최소 지원 버전: `Python 3.11`
- 최신 안정화 검증은 별도 최신 `Python 3.14.x` 환경에서도 권장
- 실무 검증은 `3.11`과 최신 안정화 버전을 각각 별도 가상환경으로 분리해 수행

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
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
```

PowerShell 실행 정책 오류가 나면(최초 1회):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

다시 활성화:

```powershell
.\.venv314\Scripts\Activate.ps1
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
python -m pdf2md .\sample.pdf
```

`-o`를 생략하면 입력 PDF와 같은 위치에 `sample_output\` 폴더가 생성됩니다.

생성 파일:
- `sample_output\document.md`
- `sample_output\manifest.json`
- `sample_output\report.json`

출력 디렉터리를 직접 지정하려면:

```powershell
python -m pdf2md .\sample.pdf -o .\output
```

### 7-1) 폴더 내 PDF 일괄 순차 변환

예시 입력 폴더: `.\pdfs`

```powershell
python -m pdf2md --input-dir .\pdfs
```

배치 모드 결과는 입력 폴더 내부 `output` 아래에 생성됩니다.

예:

- `pdfs\output\alpha\alpha.md`
- `pdfs\output\alpha\alpha_manifest.json`
- `pdfs\output\alpha\alpha_report.json`
- `pdfs\output\alpha\alpha_assets\images\...`
- `pdfs\output\batch_report.json`

배치 모드 주의사항:

- 대상은 지정 폴더 바로 아래 PDF 파일만 포함합니다.
- 배치 모드에서는 `-o/--output-dir` 을 사용하지 않습니다.
- PDF가 없는 폴더는 에러 처리됩니다.
- 같은 파일 stem을 가진 PDF가 둘 이상 있으면 충돌 방지를 위해 에러 처리됩니다.

최근 버전 기준 추가 확인 포인트:
- `manifest.json > schema_version`
- `manifest.json > images[].alt_text`
- `manifest.json > images[].caption_text`, `caption_source` (인접 캡션이 확실한 경우만)
- `manifest.json > excluded_images[].classification`
- `manifest.json > excluded_images[].recovered_text`
- `manifest.json > excluded_images[].ocr_candidates`
- `manifest.json > excluded_images[].recovery_strategy`
- `manifest.json > excluded_images[].context_validated`
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
- `summary.structure_marker_recovered_count`
- `summary.structure_marker_recovered_exact_count`
- `summary.structure_marker_recovered_context_count`
- `summary.structure_marker_suppressed_count`

배치 모드에서는 추가로 아래 파일도 확인하세요:

- `output\batch_report.json`
  - 문서별 상태
  - 문서별 출력 경로
  - 문서별 종료 코드
  - 문서별 `started_at`, `finished_at`, `duration_ms`
  - 문서별 `warning_count`, `table_count`, `image_count`, `used_ocr`, `skipped`
  - 전체 성공/실패 집계

기존 핵심 산출물이 이미 있는 문서를 건너뛰려면:

```powershell
python -m pdf2md --input-dir .\pdfs --skip-existing
```

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

구조 인덱스가 중요한 기술 문서 운영 팁:

- 최신 버전에서는 tiny 좌측 여백 구조 마커를 가능한 경우 `2.2.1`, `4.1.7` 같은 텍스트로 복구합니다.
- 문서 품질 점검 시 표 fallback뿐 아니라 구조 마커 복구도 같이 확인하는 것이 좋습니다.
- 확인 위치:
  - `document.md`: 구조 번호가 실제 heading처럼 자연스럽게 보이는지
  - `manifest.json`: `recovered_text`, `recovery_strategy`, `ocr_candidates`
  - `report.json`: `structure_marker_recovered_count`, `structure_marker_suppressed_count`

강제 OCR:

```powershell
python -m pdf2md .\sample.pdf -o .\output --force-ocr
```

로그를 자세히 보기:

```powershell
python -m pdf2md .\sample.pdf -o .\output --verbose
python -m pdf2md .\sample.pdf -o .\output --debug
```

배치 모드 예시:

```powershell
python -m pdf2md --input-dir .\pdfs
```

실행기 표기 정책:

- 이 문서는 Windows 기준이라 `python -m pdf2md`를 기본으로 사용합니다.
- README의 macOS/Linux 예시는 `python3 -m pdf2md`를 사용합니다.
- 설치형 엔트리포인트가 잡혀 있으면 `pdf2md ...`로 실행할 수 있습니다.

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

### 10-1) Python 버전별 검증 권장 절차

최소 지원 버전 `3.11`:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m pytest -q -p no:cacheprovider
python -m pdf2md --help
deactivate
```

최신 안정화 버전 `3.14`:

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m pytest -q -p no:cacheprovider
python -m pdf2md --help
deactivate
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
.\.venv314\Scripts\Activate.ps1
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

## 13) 원클릭 스크립트 상세

### A. Windows 원클릭 환경 구성 스크립트

배치 파일 진입점:

```powershell
.\scripts\setup_windows_env.bat
```

PowerShell 본체 직접 실행:

```powershell
.\scripts\setup_windows_env.ps1
```

이 스크립트가 하는 일:

1. `py -3.14 --version` 확인
2. 없으면 `winget`으로 Python 3.14 설치 시도
3. `.venv314` 생성
4. `.venv314\Scripts\python.exe -m pip install --upgrade pip`
5. `.venv314\Scripts\python.exe -m pip install -e .[dev]`
6. `.venv314\Scripts\python.exe -m pdf2md --help` 검증

지원 옵션:

```powershell
.\scripts\setup_windows_env.ps1 -PythonVersion 3.14 -VenvDir .venv314
.\scripts\setup_windows_env.ps1 -SkipWingetInstall
```

완료 후 표시되는 활성화 명령:

- PowerShell: `.\.venv314\Scripts\Activate.ps1`
- CMD: `.\.venv314\Scripts\activate.bat`

### B. 폴더 내 PDF 일괄 순차 변환 원클릭 스크립트

배치 파일 진입점:

```powershell
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

PowerShell 본체 직접 실행:

```powershell
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs
```

이 스크립트가 하는 일:

1. `.venv314\Scripts\python.exe` 확인
2. 없으면 `scripts\setup_windows_env.ps1`를 먼저 실행
3. 입력 폴더 바로 아래 PDF 존재 여부 확인
4. `python -m pdf2md --input-dir .\pdfs` 실행
5. 종료 코드와 출력 위치 요약

예시 옵션:

```powershell
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -SkipExisting
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -TableMode html -ImageMode referenced
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -Pages 1-3,5 -NoPageMarkers
```

---

## 14) 업데이트 방법

```powershell
git pull origin main
.\.venv314\Scripts\Activate.ps1
pip install -e .[dev]
```

---

## 15) 권장 실행 예시 (복사해서 바로 실행)

```powershell
git clone https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex.git
cd ConvertPdfToMarkdownWithCodex
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
python -m pdf2md .\sample.pdf -o .\output --pages 1-3 --keep-page-markers --image-mode referenced --table-mode auto
```

---

## 16) `git clone` 없이 실행하는 실전 예시

### A. 소스 ZIP만 있는 경우(인터넷 가능 환경)

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
.\scripts\setup_windows_env.bat
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

배치 결과 예시:

- `pdfs\output\alpha\alpha.md`
- `pdfs\output\alpha\alpha_manifest.json`
- `pdfs\output\alpha\alpha_report.json`
- `pdfs\output\batch_report.json`

단일 PDF만 빠르게 실행하고 싶다면:

```powershell
.\.venv314\Scripts\python.exe -m pdf2md .\sample.pdf -o .\output
```

### B. 완전 오프라인 환경(의존성 wheel 반입)

사전 준비(인터넷 가능한 환경):
- 프로젝트 소스 ZIP
- `wheelhouse` 폴더(필요 패키지 wheel 파일 모음)

사내 PC 실행:

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
pip install --no-index --find-links .\wheelhouse -e .
python -m pdf2md .\sample.pdf -o .\output
```

### C. OCR까지 필요한 경우

- `tesseract.exe`가 설치되어 있거나 PATH에 잡혀 있어야 합니다.
- 보안 환경에서는 Portable/오프라인 설치 방식으로 반입 후 아래 확인:

```powershell
tesseract --version
```
