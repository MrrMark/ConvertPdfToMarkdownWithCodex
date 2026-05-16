#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pdf2md.gui_runner import check_gui_runtime
from pdf2md.gui_support import build_gui_support_bundle, support_bundle_redaction_findings, write_gui_support_bundle


EXIT_REDACTION_FAILED = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a sanitized local-only GUI support bundle from runtime diagnostics "
            "and optional gui_smoke_evidence.json."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("gui_support_output"),
        help="Directory where gui_support_bundle.json and gui_support_bundle.md are written.",
    )
    parser.add_argument(
        "--smoke-evidence",
        type=Path,
        default=None,
        help="Optional gui_smoke_evidence.json to summarize without raw messages or paths.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the sanitized support bundle JSON to stdout.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve(strict=False)
    smoke_evidence = _load_smoke_evidence(args.smoke_evidence)
    roots = [output_dir, Path.cwd(), Path.home()]
    if args.smoke_evidence is not None:
        roots.append(args.smoke_evidence.expanduser().resolve(strict=False).parent)
    bundle = build_gui_support_bundle(
        runtime_report=check_gui_runtime(),
        smoke_evidence=smoke_evidence,
        roots=roots,
    )
    findings = support_bundle_redaction_findings(bundle, roots=roots)
    bundle["redaction_findings"] = findings
    json_path, markdown_path = write_gui_support_bundle(bundle, output_dir)
    if args.json_only:
        print(json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("GUI support bundle: " + ("failed" if findings else "passed"))
        print(f"JSON: {json_path.name}")
        print(f"Markdown: {markdown_path.name}")
        if findings:
            print("Redaction findings:")
            for finding in findings:
                print(f"- {finding['code']}")
    return EXIT_REDACTION_FAILED if findings else 0


def _load_smoke_evidence(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.expanduser().read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
