# Windows A-Z 설치/실행 가이드 (Python 3.14 기준)

이 문서는 **Windows 환경에서 `pdf2md`를 설치하고 실행하는 전체 절차**를 다룹니다.
대상: 처음 세팅하는 사용자

---

## 1) 빠른 시작

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

## 2) 사전 준비

필수:

- Windows 10/11
- PowerShell
- Python 3.14.x

선택:

- Git
  - `git clone`, `git pull` 같은 저장소 동기화 흐름에서만 필요
  - ZIP 배포본 + 원클릭 스크립트 경로에서는 필수가 아님
- Tesseract OCR
  - OCR 기능 사용 시 필요

---

## 3) Python 3.14 설치

1. [Python 3.14 다운로드](https://www.python.org/downloads/windows/)
2. 설치 시 `Add python.exe to PATH` 체크
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

## 4) 저장소 받기

### A. ZIP 배포본 사용

ZIP을 압축 해제한 뒤 작업 폴더로 이동합니다.

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
```

### B. Git으로 clone

Git 기반으로 작업하려면 아래처럼 실행합니다.

```powershell
git clone https://github.com/MrrMark/ConvertPdfToMarkdownWithCodex.git
cd ConvertPdfToMarkdownWithCodex
```

### C. 회사 보안 환경에서 `git clone`이 막힌 경우

대체 경로:

1. 소스 ZIP 반입
2. 사내 미러/아티팩트 저장소 사용
3. 소스 ZIP + `wheelhouse` + 설치 스크립트로 구성된 릴리스 번들 사용

---

## 5) 환경 구성

수동으로 환경을 만들려면:

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
python -m pdf2md --help
```

PowerShell 실행 정책 오류가 나면:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

원클릭 스크립트 사용 시:

```powershell
.\scripts\setup_windows_env.bat
```

이 스크립트가 하는 일:

1. `py -3.14 --version` 확인
2. 없으면 `winget`으로 Python 3.14 설치 시도
3. `.venv314` 생성
4. `.venv314\Scripts\python.exe -m pip install --upgrade pip`
5. `.venv314\Scripts\python.exe -m pip install -e .[dev]`
6. `.venv314\Scripts\python.exe -m pdf2md --help` 검증

직접 PowerShell로 실행할 수도 있습니다.

```powershell
.\scripts\setup_windows_env.ps1 -PythonVersion 3.14 -VenvDir .venv314
.\scripts\setup_windows_env.ps1 -SkipWingetInstall
```

완료 후 활성화 명령:

- PowerShell: `.\.venv314\Scripts\Activate.ps1`
- CMD: `.\.venv314\Scripts\activate.bat`

---

## 6) 기본 실행

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

비밀번호 PDF:

```powershell
python -m pdf2md .\sample.pdf -o .\output --password secret
```

강제 OCR:

```powershell
python -m pdf2md .\sample.pdf -o .\output --force-ocr
```

페이지 범위:

```powershell
python -m pdf2md .\sample.pdf -o .\output --pages 1-3,5
```

페이지 마커:

```powershell
python -m pdf2md .\sample.pdf -o .\output --keep-page-markers
python -m pdf2md .\sample.pdf -o .\output --no-page-markers
```

표 모드:

```powershell
python -m pdf2md .\sample.pdf -o .\output --table-mode auto
python -m pdf2md .\sample.pdf -o .\output --table-mode html
python -m pdf2md .\sample.pdf -o .\output --table-mode markdown
```

이미지 모드:

```powershell
python -m pdf2md .\sample.pdf -o .\output --image-mode referenced
```

로그 보기:

```powershell
python -m pdf2md .\sample.pdf -o .\output --verbose
python -m pdf2md .\sample.pdf -o .\output --debug
```

---

## 7) 폴더 내 PDF 일괄 순차 변환

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

기존 핵심 산출물이 이미 있는 문서를 건너뛰려면:

```powershell
python -m pdf2md --input-dir .\pdfs --skip-existing
```

`batch_report.json`에서 확인할 핵심 값:

- 문서별 상태: `success`, `partial_success`, `failed`, `skipped`
- 문서별 출력 경로
- 문서별 종료 코드
- 문서별 `warning_count`, `table_count`, `image_count`, `used_ocr`, `skipped`

`--skip-existing`를 사용하면 다시 처리하지 않은 문서는 `status == "skipped"` 와 `skipped == true`로 기록됩니다.

원클릭 배치 스크립트:

```powershell
.\scripts\run_batch_folder_windows.bat -InputDir .\pdfs
```

PowerShell 본체 직접 실행:

```powershell
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs
```

예시 옵션:

```powershell
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -SkipExisting
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -TableMode html -ImageMode referenced
.\scripts\run_batch_folder_windows.ps1 -InputDir .\pdfs -Pages 1-3,5 -NoPageMarkers
```

---

## 8) OCR 사용

`--force-ocr` 또는 텍스트 없는 페이지 OCR을 사용하려면 Tesseract가 필요합니다.

1. Windows용 Tesseract 설치
2. 설치 경로를 PATH에 추가
3. 확인

```powershell
tesseract --version
```

정상 출력되면 OCR 기능 사용 가능

---

## 9) 심화 운영 점검 포인트

`manifest.json`에서 확인할 항목:

- `schema_version`
- `images[].alt_text`
- `images[].caption_text`, `caption_source`
- `excluded_images[].classification`
- `excluded_images[].recovered_text`
- `excluded_images[].ocr_candidates`
- `excluded_images[].recovery_strategy`
- `excluded_images[].context_validated`

`report.json`에서 확인할 항목:

- `schema_version`
- `page_results[].status`
- `summary.page_status_counts`
- `summary.table_fallback_count`
- `summary.table_fallbacks`
- `summary.table_mode_requested`
- `summary.table_markdown_forced_count`
- `summary.table_html_forced_count`
- `summary.structure_marker_recovered_count`
- `summary.structure_marker_recovered_exact_count`
- `summary.structure_marker_recovered_context_count`
- `summary.structure_marker_suppressed_count`

구조 인덱스가 중요한 기술 문서 운영 팁:

- tiny 좌측 여백 구조 마커를 가능한 경우 `2.2.1`, `4.1.7` 같은 텍스트로 복구합니다.
- 문서 품질 점검 시 표 fallback뿐 아니라 구조 마커 복구도 같이 확인하는 것이 좋습니다.
- 확인 위치:
  - `document.md`
  - `manifest.json`
  - `report.json`

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
- `2`: 부분 성공

`2`는 실패가 아니라, 일부 warning이나 fallback이 포함된 정상 실행일 수 있습니다.

---

## 12) 트러블슈팅

### A. `python` 명령이 안 잡힘

- Python 설치 시 PATH 체크 누락 가능
- 새 PowerShell 재실행
- `py -3.11 --version`, `py -3.14 --version`으로 확인

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

- `referenced` 모드에서만 실제 이미지 파일을 저장합니다.
- `embedded`는 Markdown 내부 data URI, `placeholder`는 comment만 남깁니다.

### F. 표가 기대보다 많거나 적게 추출됨

- `report.json > summary.table_*`와 `warnings[].details.reasons`를 우선 확인하세요.
- `markdown` 모드에서는 복잡 표도 Markdown으로 강제되므로 일부 구조 손실이 있을 수 있습니다.

### G. 권한 문제

- 회사 보안 정책으로 스크립트 실행이 제한될 수 있습니다.
- PowerShell 정책 또는 보안 솔루션 정책을 확인하세요.

---

## 13) 업데이트 방법

Git 기반 작업 시:

```powershell
git pull origin main
.\.venv314\Scripts\Activate.ps1
pip install -e .[dev]
```

ZIP 배포본 사용 시:

- 새 ZIP을 다시 받아 교체한 뒤
- `.\scripts\setup_windows_env.bat` 또는 수동 설치 절차를 재실행

---

## 14) `git clone` 없이 실행하는 실전 예시

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

사전 준비:

- 프로젝트 소스 ZIP
- `wheelhouse` 폴더

사내 PC 실행:

```powershell
cd C:\Work\ConvertPdfToMarkdownWithCodex
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
pip install --no-index --find-links .\wheelhouse -e .
python -m pdf2md .\sample.pdf -o .\output
```
