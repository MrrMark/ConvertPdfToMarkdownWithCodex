from __future__ import annotations

from pdf2md.models import Manifest


def serialize_manifest(manifest: Manifest) -> dict:
    return manifest.model_dump(mode="json")
