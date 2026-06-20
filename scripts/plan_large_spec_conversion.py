#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pdf2md.preflight import PreflightOptions, plan_large_spec_conversion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan conservative pdf2md options for a large technical spec PDF.")
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("--pages", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--sample-page-count", type=int, default=5)
    parser.add_argument("--domain-adapter", default=None)
    parser.add_argument("--prefer-visual", action="store_true")
    parser.add_argument("--prefer-assetless", action="store_true")
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args(argv)

    report = plan_large_spec_conversion(
        args.input_pdf,
        PreflightOptions(
            pages=args.pages,
            password=args.password,
            sample_page_count=args.sample_page_count,
            domain_adapter=args.domain_adapter,
            prefer_visual=args.prefer_visual,
            prefer_assetless=args.prefer_assetless,
        ),
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report_path is not None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.report_path}")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
