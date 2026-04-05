from __future__ import annotations

from pdf2md.models import Report


def serialize_report(report: Report) -> dict:
    return report.model_dump(mode="json")
