from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_output_dirs(output_dir: Path, assets_dirname: str = "assets") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / assets_dirname).mkdir(parents=True, exist_ok=True)
    (output_dir / assets_dirname / "images").mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
