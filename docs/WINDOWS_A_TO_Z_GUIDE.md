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

강제 OCR:

```powershell
python -m pdf2md .\sample.pdf -o .\output --force-ocr
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

### E. 권한 문제
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

