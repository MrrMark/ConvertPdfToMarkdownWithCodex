from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pdf2md.models import (
    ArtifactIntegrityReport,
    BatchReport,
    CorpusEvidenceAnalysisReport,
    CorpusEvidenceTrendReport,
    CorpusDiffReport,
    CorpusManifest,
    IndexContractReport,
    LocalCorpusEvidencePack,
    Manifest,
    ProvenanceIntegrityReport,
    Report,
    RequirementChangeImpactReport,
)


SCHEMA_FILES: dict[str, type] = {
    "manifest.schema.json": Manifest,
    "report.schema.json": Report,
    "batch_report.schema.json": BatchReport,
    "corpus_manifest.schema.json": CorpusManifest,
    "corpus_diff_report.schema.json": CorpusDiffReport,
    "requirement_change_impact_report.schema.json": RequirementChangeImpactReport,
    "index_contract_report.schema.json": IndexContractReport,
    "provenance_integrity_report.schema.json": ProvenanceIntegrityReport,
    "artifact_integrity_report.schema.json": ArtifactIntegrityReport,
    "local_corpus_evidence_pack.schema.json": LocalCorpusEvidencePack,
    "corpus_evidence_analysis_report.schema.json": CorpusEvidenceAnalysisReport,
    "corpus_evidence_trend_report.schema.json": CorpusEvidenceTrendReport,
}


def generate_schema_documents() -> dict[str, dict[str, Any]]:
    """Generate JSON Schema documents for stable public JSON outputs."""
    return {filename: model.model_json_schema() for filename, model in SCHEMA_FILES.items()}


def serialize_schema(payload: dict[str, Any]) -> str:
    """Serialize schema with stable formatting and LF."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_schema_files(output_dir: Path) -> list[Path]:
    """Write all output schema files and return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, payload in generate_schema_documents().items():
        path = output_dir / filename
        path.write_text(serialize_schema(payload), encoding="utf-8")
        written.append(path)
    return written


def check_schema_files(output_dir: Path) -> list[str]:
    """Return mismatch descriptions for missing or stale schema files."""
    mismatches: list[str] = []
    for filename, payload in generate_schema_documents().items():
        path = output_dir / filename
        expected = serialize_schema(payload)
        if not path.exists():
            mismatches.append(f"missing: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            mismatches.append(f"stale: {path}")
    return mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export machine-readable pdf2md output JSON Schemas")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/schema"),
        help="Directory where schema JSON files are written.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate committed schema files without writing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        mismatches = check_schema_files(args.output_dir)
        if mismatches:
            for mismatch in mismatches:
                print(mismatch)
            return 1
        print(f"schema files are current: {args.output_dir}")
        return 0

    written = write_schema_files(args.output_dir)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
