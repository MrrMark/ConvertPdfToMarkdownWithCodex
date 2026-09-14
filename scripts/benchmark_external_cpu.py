"""Q157 optional CPU adapters; imported only in isolated engine workers."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

PINS = {
    "docling": ("docling", "2.126.0"),
    "marker": ("marker-pdf", "2.0.0"),
    "pymupdf": ("pymupdf4llm", "1.27.2.2"),
}


class ExternalUnavailable(ImportError):
    """Carry a safe, reproducible prerequisite failure without document content."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def chunk_counts(chunks: list[dict]) -> dict:
    """Count classified layout boxes, not text occurrences or JSON key matches."""
    boxes = [box for page in chunks for box in page["page_boxes"]]
    return {
        "pages": len(chunks),
        "tables": sum(box["class"] == "table" for box in boxes),
        "pictures": sum(box["class"] == "picture" for box in boxes),
    }


def prepare_external(engine: str, request: dict):
    """Prepare a local engine; never silently change Marker fast's OCR behavior."""
    if engine == "marker":
        # Marker 2.0 fast may still call its local VLM. Disabling OCR would
        # benchmark a different configuration, so stop before any lazy downloads.
        if shutil.which("llama-server") is None:
            raise ExternalUnavailable("marker_fast_requires_local_llama_server_missing")
        raise ExternalUnavailable("marker_fast_model_and_server_preprovisioning_required")
    if engine != "pymupdf":
        raise ValueError(f"Unsupported external engine: {engine}")

    import onnxruntime as ort

    # The pinned library creates sessions during import and exposes no session
    # options parameter. Constrain those sessions before its layout import.
    original_session = ort.InferenceSession
    sessions = []

    def cpu_session(path, sess_options=None, providers=None, **kwargs):
        options = sess_options or ort.SessionOptions()
        options.intra_op_num_threads = request["threads"]
        options.inter_op_num_threads = 1
        session = original_session(path, sess_options=options, providers=["CPUExecutionProvider"], **kwargs)
        sessions.append(session)
        return session

    ort.InferenceSession = cpu_session
    try:
        import pymupdf4llm
        import pymupdf.layout
    finally:
        ort.InferenceSession = original_session
    if not sessions:
        raise ExternalUnavailable("pymupdf_layout_sessions_not_initialized")
    from scripts.benchmark_fair_comparison import model_identity

    info = {
        "models": model_identity(Path(pymupdf.layout.__file__).parent, suffix=".onnx"),
        "effective_options": {
            "layout": True, "page_chunks": True, "write_images": True,
            "use_ocr": True, "ocr_language": "eng", "header": True, "footer": True,
            "onnx_providers": [session.get_providers() for session in sessions],
            "onnx_intra_op_threads": request["threads"], "onnx_inter_op_threads": 1,
        },
        "initialization_note": "layout_model_initialization_in_import_seconds",
        "count_semantics": "layout_boxes_including_table_fallback; not_native_semantic_objects",
    }

    def convert(source: Path, output: Path) -> dict:
        chunks = pymupdf4llm.to_markdown(
            str(source), page_chunks=True, write_images=True, image_path=str(output / "images"),
            use_ocr=True, ocr_language="eng", show_progress=False,
        )
        (output / "document.md").write_text("\n\n".join(page["text"] for page in chunks), encoding="utf-8")
        (output / "document.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        return chunk_counts(chunks)

    return convert, info
