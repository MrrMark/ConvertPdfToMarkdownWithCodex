# GUI 사용자 가이드

이 파일은 wheel/sdist 설치 환경에서 GUI `Help` 기능과 runtime doctor가 사용할 수 있는 packaged fallback 문서다.

소스 checkout에서는 `docs/GUI_USER_GUIDE.md`가 우선 사용된다. 설치된 wheel에서 repository-level `docs/` 파일을 사용할 수 없는 경우 이 package resource가 help document availability 계약을 유지한다.

## 실행

```bash
python -m pdf2md.gui
python -m pdf2md.gui --help
python -m pdf2md.gui --doctor --doctor-format json
```

`--doctor`는 Tk window를 띄우지 않고 Python/Tkinter, optional OCR runtime, package metadata, entry point, help document 상태를 구조화된 diagnostic으로 출력한다. 실제 Tk window 생성까지 확인해야 하는 desktop session에서는 `--doctor-check-window`를 명시한다.

## 변환 원칙

- 텍스트는 요약, 재서술, 교정 없이 원문 보존을 우선한다.
- 단순 표만 Markdown table로 출력하고 복잡하거나 애매한 표는 HTML fallback을 우선한다.
- 이미지는 기본적으로 referenced mode로 별도 파일에 저장하고 Markdown에서 상대경로로 참조한다.
- 실패는 숨기지 않고 `report.json`, GUI summary, support artifact에 구조화된 code/count 중심으로 기록한다.
- 폴더 배치에서는 previous corpus manifest와 reuse unchanged를 사용해 CLI incremental corpus 흐름과 같은 `corpus_diff_report.json`, `requirement_change_impact_report.json`을 생성할 수 있다.
- previous corpus manifest path는 GUI profile이나 recent state에 저장하지 않는다.

## Local-only 지원 artifact

GUI smoke evidence와 support bundle은 public output schema가 아니라 local-only 지원 artifact다. 원문 PDF 텍스트, Markdown 본문, 표/이미지 내용, 변환 warning message, absolute path를 저장하지 않고 status count, warning code/count, sanitized artifact label, runtime diagnostic code 중심으로 기록한다.
