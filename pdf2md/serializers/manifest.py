from __future__ import annotations

from pdf2md.models import Manifest


def serialize_manifest(manifest: Manifest) -> dict:
    payload = manifest.model_dump(mode="json")
    for asset in payload.get("images", []):
        if asset.get("source_text_lines") is None:
            asset.pop("source_text_lines", None)
    for asset in payload.get("tables", []):
        if asset.get("cell_structure") is None:
            asset.pop("cell_structure", None)
    return payload
