#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


WORKFLOW_PROFILES = {
    "preserve": "preserve",
    "rag-optimized": "rag_optimized",
    "technical-rag": "technical_spec_rag",
    "visual-technical-rag": "technical_spec_rag_visual",
    "confidential-rag": "confidential_rag",
    "preserve-with-sidecars": "preserve_with_sidecars",
    "assetless-technical-rag": "technical_spec_rag_visual",
}
TECHNICAL_WORKFLOWS = {"technical-rag", "visual-technical-rag", "assetless-technical-rag"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.project_root.resolve() if args.project_root else find_project_root(Path.cwd())
    python = select_python(root)

    if args.command == "doctor":
        return run_doctor(args, root, python)
    if args.command == "convert":
        return run_convert(args, root, python)
    if args.command == "validate":
        return run_validate(args, root, python)
    parser.error(f"unknown command: {args.command}")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent-friendly wrapper for common pdf2md workflows.")
    parser.add_argument("--project-root", type=Path, default=None, help="Repository root. Defaults to walking up from cwd.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check that pdf2md and optional OCR runtime are visible.")
    doctor.add_argument("--ocr-lang", default="eng")
    doctor.add_argument("--skip-ocr-check", action="store_true", default=False)
    doctor.add_argument("--dry-run", action="store_true", default=False)

    convert = subparsers.add_parser("convert", help="Run a single-file or batch conversion.")
    convert.add_argument("input_pdf", nargs="?", type=Path)
    convert.add_argument("--input-dir", type=Path, default=None)
    convert.add_argument("-o", "--output-dir", type=Path, default=None)
    convert.add_argument(
        "--workflow",
        choices=sorted(WORKFLOW_PROFILES),
        default="preserve",
        help="High-level workflow mapped to a pdf2md RAG profile.",
    )
    convert.add_argument("--domain-adapter", default=None)
    convert.add_argument("--pages", default=None)
    convert.add_argument("--password", default=None)
    convert.add_argument("--ocr-lang", default=None)
    convert.add_argument("--force-ocr", action="store_true", default=False)
    convert.add_argument("--rag-table-output", choices=("none", "markdown", "jsonl", "both"), default=None)
    convert.add_argument("--page-workers", type=int, default=None)
    convert.add_argument("--skip-existing", action="store_true", default=False)
    convert.add_argument("--previous-corpus-manifest", type=Path, default=None)
    convert.add_argument("--reuse-unchanged", action="store_true", default=False)
    convert.add_argument("--dry-run", action="store_true", default=False)

    validate = subparsers.add_parser("validate", help="Run local-only validators against an output directory.")
    validate.add_argument("--output-dir", required=True, type=Path)
    validate.add_argument("--target", default="all")
    validate.add_argument("--confidential-safe", action="store_true", default=False)
    validate.add_argument("--fail-on-warning", action="store_true", default=False)
    validate.add_argument("--dry-run", action="store_true", default=False)
    return parser


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "pdf2md").is_dir():
            return candidate
    return start


def select_python(root: Path) -> str:
    explicit = os.environ.get("PDF2MD_PYTHON")
    if explicit:
        return explicit
    candidates = [
        root / ".venv311" / "bin" / "python",
        root / ".venv314" / "bin" / "python",
        root / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("python3") or shutil.which("python") or "python3"


def run_doctor(args: argparse.Namespace, root: Path, python: str) -> int:
    commands = [[python, "-m", "pdf2md", "--help"]]
    ocr_check = root / "scripts" / "check_ocr_runtime.py"
    if not args.skip_ocr_check and ocr_check.exists():
        commands.append([python, str(ocr_check), "--ocr-lang", args.ocr_lang])
    return run_many(commands, root, dry_run=args.dry_run)


def run_convert(args: argparse.Namespace, root: Path, python: str) -> int:
    if (args.input_pdf is None) == (args.input_dir is None):
        raise SystemExit("Provide exactly one of input_pdf or --input-dir.")
    command = [python, "-m", "pdf2md"]
    if args.input_dir is not None:
        command.extend(["--input-dir", str(args.input_dir)])
        if args.output_dir is not None:
            raise SystemExit("--output-dir is not supported with --input-dir batch conversion")
    else:
        command.append(str(args.input_pdf))
        if args.output_dir is not None:
            command.extend(["--output-dir", str(args.output_dir)])

    command.extend(["--rag-profile", WORKFLOW_PROFILES[args.workflow]])
    if args.workflow in TECHNICAL_WORKFLOWS:
        if not args.domain_adapter:
            raise SystemExit(f"--domain-adapter is required for workflow {args.workflow}")
        command.extend(["--domain-adapter", args.domain_adapter])
    elif args.domain_adapter:
        command.extend(["--domain-adapter", args.domain_adapter])

    if args.workflow == "assetless-technical-rag":
        command.extend(["--image-mode", "placeholder"])
    if args.pages:
        command.extend(["--pages", args.pages])
    if args.password:
        command.extend(["--password", args.password])
    if args.ocr_lang:
        command.extend(["--ocr-lang", args.ocr_lang])
    if args.force_ocr:
        command.append("--force-ocr")
    if args.rag_table_output:
        command.extend(["--rag-table-output", args.rag_table_output])
    if args.page_workers is not None:
        command.extend(["--page-workers", str(args.page_workers)])
    if args.skip_existing:
        command.append("--skip-existing")
    if args.previous_corpus_manifest:
        command.extend(["--previous-corpus-manifest", str(args.previous_corpus_manifest)])
    if args.reuse_unchanged:
        command.append("--reuse-unchanged")
    return run_many([command], root, dry_run=args.dry_run)


def run_validate(args: argparse.Namespace, root: Path, python: str) -> int:
    output_dir = str(args.output_dir)
    commands: list[list[str]] = []
    index_validator = root / "scripts" / "validate_index_contract.py"
    provenance_validator = root / "scripts" / "validate_provenance_integrity.py"
    artifact_validator = root / "scripts" / "validate_artifact_integrity.py"

    if index_validator.exists():
        command = [
            python,
            str(index_validator),
            "--output-dir",
            output_dir,
            "--target",
            args.target,
            "--fail-on-error",
        ]
        if args.confidential_safe:
            command.append("--confidential-safe")
        if args.fail_on_warning:
            command.append("--fail-on-warning")
        commands.append(command)
    if provenance_validator.exists():
        commands.append([python, str(provenance_validator), "--output-dir", output_dir, "--fail-on-error"])
    if artifact_validator.exists():
        commands.append([python, str(artifact_validator), "--output-dir", output_dir, "--fail-on-error"])
    if not commands:
        print("No pdf2md validators found under scripts/.", file=sys.stderr)
        return 1
    return run_many(commands, root, dry_run=args.dry_run)


def run_many(commands: list[list[str]], cwd: Path, *, dry_run: bool) -> int:
    exit_code = 0
    for command in commands:
        print("+ " + " ".join(command))
        if dry_run:
            continue
        completed = subprocess.run(command, cwd=cwd, check=False)
        if completed.returncode != 0 and exit_code == 0:
            exit_code = completed.returncode
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
