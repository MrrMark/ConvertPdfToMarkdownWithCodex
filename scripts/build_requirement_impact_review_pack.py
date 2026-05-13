from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


JSON_FILENAME = "requirement_impact_review_pack.json"
MARKDOWN_FILENAME = "requirement_impact_review_pack.md"


def _status_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"added": 0, "changed": 0, "removed": 0}
    for entry in entries:
        status = str(entry.get("status") or "")
        if status in counts:
            counts[status] += 1
    return counts


def _first_text(values: list[Any]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _preview(text: str, *, limit: int = 180) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


def _pages(source_refs: list[dict[str, Any]]) -> list[int]:
    pages = sorted(
        {
            int(ref["page"])
            for ref in source_refs
            if isinstance(ref, dict) and isinstance(ref.get("page"), int)
        }
    )
    return pages


def _source_ids(source_refs: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    ids: list[str] = []
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        source_id = str(ref.get("source_id") or "").strip()
        if source_id and source_id not in ids:
            ids.append(source_id)
        if len(ids) >= limit:
            break
    return ids


def _recommendation(status: str, changed_fields: list[str]) -> str:
    if status == "added":
        return "create_or_extend_test_coverage"
    if status == "removed":
        return "review_obsolete_tests_and_trace_links"
    if "texts" in changed_fields:
        return "review_test_logic_and_expected_results"
    if "source_refs" in changed_fields:
        return "verify_citation_and_traceability_only"
    return "review_requirement_metadata"


def _review_item(entry: dict[str, Any], index: int) -> dict[str, Any]:
    previous_source_refs = [ref for ref in entry.get("previous_source_refs") or [] if isinstance(ref, dict)]
    current_source_refs = [ref for ref in entry.get("current_source_refs") or [] if isinstance(ref, dict)]
    previous_text = _first_text(list(entry.get("previous_texts") or []))
    current_text = _first_text(list(entry.get("current_texts") or []))
    changed_fields = [str(field) for field in entry.get("changed_fields") or []]
    status = str(entry.get("status") or "unknown")
    return {
        "review_id": f"impact-{index:04d}",
        "doc_id": str(entry.get("doc_id") or ""),
        "requirement_key": str(entry.get("requirement_key") or ""),
        "requirement_id": entry.get("requirement_id"),
        "status": status,
        "changed_fields": changed_fields,
        "recommendation": _recommendation(status, changed_fields),
        "previous_text_preview": _preview(previous_text),
        "current_text_preview": _preview(current_text),
        "previous_trace_ids": list(entry.get("previous_trace_ids") or []),
        "current_trace_ids": list(entry.get("current_trace_ids") or []),
        "previous_source_ref_count": len(previous_source_refs),
        "current_source_ref_count": len(current_source_refs),
        "previous_pages": _pages(previous_source_refs),
        "current_pages": _pages(current_source_refs),
        "previous_source_ids": _source_ids(previous_source_refs),
        "current_source_ids": _source_ids(current_source_refs),
        "previous_source_refs": previous_source_refs,
        "current_source_refs": current_source_refs,
    }


def build_review_pack(impact_report: dict[str, Any], *, source_report: str) -> dict[str, Any]:
    """Build a deterministic reviewer/agent summary from a requirement impact report."""
    entries = [entry for entry in impact_report.get("entries") or [] if isinstance(entry, dict)]
    review_items = [_review_item(entry, index) for index, entry in enumerate(entries, start=1)]
    status_counts = _status_counts(entries)
    return {
        "schema_version": "1.0",
        "purpose": "rag_requirement_impact_review_pack",
        "source_report": source_report,
        "previous_manifest": impact_report.get("previous_manifest"),
        "current_manifest": impact_report.get("current_manifest"),
        "summary": {
            "total_review_items": len(review_items),
            "status_counts": status_counts,
            "documents_with_changes": len({item["doc_id"] for item in review_items}),
            "changed_field_counts": {
                field: sum(1 for item in review_items if field in item["changed_fields"])
                for field in sorted({field for item in review_items for field in item["changed_fields"]})
            },
        },
        "review_items": review_items,
    }


def render_markdown(pack: dict[str, Any]) -> str:
    summary = pack.get("summary") or {}
    counts = summary.get("status_counts") or {}
    lines = [
        "# Requirement Impact Review Pack",
        "",
        f"- Source report: `{pack.get('source_report')}`",
        f"- Total review items: {summary.get('total_review_items', 0)}",
        f"- Documents with changes: {summary.get('documents_with_changes', 0)}",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    for status in ("added", "changed", "removed"):
        lines.append(f"| {status} | {int(counts.get(status) or 0)} |")
    lines.extend(
        [
            "",
            "| Review ID | Status | Doc | Requirement | Changed Fields | Recommendation | Current Pages |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in pack.get("review_items") or []:
        pages = ", ".join(str(page) for page in item.get("current_pages") or item.get("previous_pages") or [])
        changed_fields = ", ".join(item.get("changed_fields") or [])
        requirement = item.get("requirement_id") or item.get("requirement_key") or ""
        lines.append(
            "| {review_id} | {status} | {doc_id} | {requirement} | {changed_fields} | {recommendation} | {pages} |".format(
                review_id=item.get("review_id"),
                status=item.get("status"),
                doc_id=item.get("doc_id"),
                requirement=requirement,
                changed_fields=changed_fields or "-",
                recommendation=item.get("recommendation"),
                pages=pages or "-",
            )
        )
    for item in pack.get("review_items") or []:
        requirement = item.get("requirement_id") or item.get("requirement_key") or ""
        lines.extend(
            [
                "",
                f"## {item.get('review_id')} {requirement}",
                "",
                f"- Status: {item.get('status')}",
                f"- Recommendation: {item.get('recommendation')}",
                f"- Previous: {_preview(str(item.get('previous_text_preview') or '')) or '-'}",
                f"- Current: {_preview(str(item.get('current_text_preview') or '')) or '-'}",
                f"- Previous source ids: {', '.join(item.get('previous_source_ids') or []) or '-'}",
                f"- Current source ids: {', '.join(item.get('current_source_ids') or []) or '-'}",
            ]
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a reviewer-friendly pack from requirement_change_impact_report.json.")
    parser.add_argument("--impact-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--json-filename", default=JSON_FILENAME)
    parser.add_argument("--markdown-filename", default=MARKDOWN_FILENAME)
    args = parser.parse_args(argv)

    impact_report = json.loads(args.impact_report.read_text(encoding="utf-8"))
    output_dir = args.output_dir or args.impact_report.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = build_review_pack(impact_report, source_report=str(args.impact_report))
    json_path = output_dir / args.json_filename
    markdown_path = output_dir / args.markdown_filename
    json_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(pack), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
