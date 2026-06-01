#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Sequence


REQUIRED_WHEEL_MEMBERS = (
    "pdf2md/py.typed",
    "pdf2md/gui.py",
    "pdf2md/gui_help.py",
    "pdf2md/gui_runner.py",
    "pdf2md/gui_support.py",
    "pdf2md/gui_profiles.py",
    "pdf2md/resources/GUI_USER_GUIDE.md",
)
REQUIRED_CONSOLE_SCRIPTS = {
    "pdf2md": "pdf2md.cli:main",
    "pdf2md-gui": "pdf2md.gui:main",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect built wheel contents for pdf2md packaging contracts.")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--report-file", type=Path, default=None)
    return parser


def inspect_wheel_contract(dist_dir: Path) -> dict[str, Any]:
    """Inspect the newest pdf2md wheel in dist_dir for GUI packaging contract files."""
    wheel_path = _newest_wheel(dist_dir)
    checks: list[dict[str, Any]] = []
    if wheel_path is None:
        return _payload(None, [{"name": "wheel_exists", "status": "failed", "message": "No pdf2md wheel found."}])
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        checks.extend(_member_checks(names))
        checks.extend(_entry_point_checks(wheel, names))
    return _payload(wheel_path, checks)


def write_report(payload: dict[str, Any], report_file: Path) -> None:
    """Write a deterministic wheel contract report."""
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _newest_wheel(dist_dir: Path) -> Path | None:
    wheels = sorted(dist_dir.glob("pdf2md-*.whl"), key=lambda path: (path.stat().st_mtime_ns, path.name))
    return wheels[-1] if wheels else None


def _member_checks(names: set[str]) -> list[dict[str, str]]:
    checks = []
    for member in REQUIRED_WHEEL_MEMBERS:
        checks.append(
            {
                "name": f"wheel_member:{member}",
                "status": "passed" if member in names else "failed",
                "message": "present" if member in names else "missing",
            }
        )
    return checks


def _entry_point_checks(wheel: zipfile.ZipFile, names: set[str]) -> list[dict[str, str]]:
    entry_point_name = next((name for name in sorted(names) if name.endswith(".dist-info/entry_points.txt")), None)
    if entry_point_name is None:
        return [{"name": "console_scripts_metadata", "status": "failed", "message": "entry_points.txt missing"}]
    entry_points = wheel.read(entry_point_name).decode("utf-8")
    checks = [{"name": "console_scripts_metadata", "status": "passed", "message": entry_point_name}]
    for script_name, target in sorted(REQUIRED_CONSOLE_SCRIPTS.items()):
        needle = f"{script_name} = {target}"
        checks.append(
            {
                "name": f"console_script:{script_name}",
                "status": "passed" if needle in entry_points else "failed",
                "message": "present" if needle in entry_points else "missing",
            }
        )
    return checks


def _payload(wheel_path: Path | None, checks: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [check for check in checks if check["status"] != "passed"]
    return {
        "schema_version": "1.0",
        "kind": "wheel_contract_report",
        "local_only": True,
        "wheel": str(wheel_path) if wheel_path is not None else None,
        "status": "failed" if failures else "passed",
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failures),
        },
        "checks": checks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = inspect_wheel_contract(args.dist_dir)
    report_file = args.report_file or args.dist_dir / "wheel_contract_report.json"
    write_report(payload, report_file)
    print(f"Wrote {report_file}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
