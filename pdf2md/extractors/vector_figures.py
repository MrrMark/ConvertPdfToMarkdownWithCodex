"""Conservative framed-vector diagram detection from original PDF geometry."""
from __future__ import annotations

from typing import Any

from pdf2md.models import LineType
from pdf2md.utils.structure import classify_structure_line

GEOMETRY_TOLERANCE = 1.0
CAPTION_MAX_GAP = 40.0
MIN_NODE_SIZE = 12.0
MIN_FRAME_WIDTH = 100.0
MIN_FRAME_HEIGHT = 24.0
MAX_FRAME_AREA_RATIO = 0.5


def contains_bbox(outer: list[float], inner: list[float], tolerance: float = GEOMETRY_TOLERANCE) -> bool:
    """Require full containment so adjacent prose is not treated as figure text."""
    return (outer[0] - tolerance <= inner[0] and outer[1] - tolerance <= inner[1]
            and outer[2] + tolerance >= inner[2] and outer[3] + tolerance >= inner[3])


def _bbox(shape: dict[str, Any]) -> list[float]:
    return [float(shape[key]) for key in ("x0", "top", "x1", "bottom")]


def _overlaps(a: list[float], b: list[float]) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _rectangular_curve(shape: dict[str, Any]) -> bool:
    points = shape.get("pts") or []
    if len(points) != 5:
        return False
    if any(abs(points[0][axis] - points[-1][axis]) > GEOMETRY_TOLERANCE for axis in (0, 1)):
        return False
    return all(abs(a[0]-b[0]) <= GEOMETRY_TOLERANCE or abs(a[1]-b[1]) <= GEOMETRY_TOLERANCE
               for a, b in zip(points, points[1:]))


def detect_framed_vector_figures(
    page: Any, *, text_lines: list[dict], confirmed_table_bboxes: list[list[float]],
    diagnostics: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Require a caption, closed frame, two enclosed nodes and a node connector.

    A rejected table is never sufficient evidence. Real table intersections and
    ambiguous caption-to-frame matches are conservatively excluded.
    """
    caption_lines = [line for line in text_lines
                     if classify_structure_line(str(line.get("text", ""))) is LineType.FIGURE_CAPTION]
    if not caption_lines:
        return []
    shapes = list(page.rects) + [shape for shape in page.curves if _rectangular_curve(shape)]
    boxes = {tuple(round(value, 2) for value in _bbox(shape)) for shape in shapes
             if float(shape["width"]) >= MIN_NODE_SIZE and float(shape["height"]) >= MIN_NODE_SIZE}
    rectangles = [list(box) for box in sorted(boxes, key=lambda box: (box[1], box[0], box[2], box[3]))]
    candidates = []
    for frame in rectangles:
        width, height = frame[2]-frame[0], frame[3]-frame[1]
        if width < MIN_FRAME_WIDTH or height < MIN_FRAME_HEIGHT or width*height > page.width*page.height*MAX_FRAME_AREA_RATIO:
            continue
        if any(_overlaps(frame, table) for table in confirmed_table_bboxes):
            continue
        nodes = [box for box in rectangles if box != frame and contains_bbox(frame, box, -GEOMETRY_TOLERANCE)]
        if len(nodes) < 2:
            continue
        connected = False
        for line in page.lines:
            if not contains_bbox(frame, _bbox(line)):
                continue
            # PDF line points preserve diagonal direction; bbox corners do not.
            points = line.get("pts") or [(line["x0"], line["top"]), (line["x1"], line["bottom"])]
            start, end = points[0], points[-1]
            for first in nodes:
                if not contains_bbox(first, [*start, *start], 2.0):
                    continue
                if any(second != first and contains_bbox(second, [*end, *end], 2.0) for second in nodes):
                    connected = True
                    break
            if connected:
                break
        if not connected:
            continue
        captions = [line for line in caption_lines
                    if 0 <= frame[1] - float(line["bottom"]) <= CAPTION_MAX_GAP
                    and min(frame[2], float(line["x1"])) > max(frame[0], float(line["x0"]))]
        if not captions:
            continue
        caption = max(captions, key=lambda line: float(line["bottom"]))
        source_lines = [{"line_index": index, "text": str(line.get("text", "")), "bbox": _bbox(line)}
                        for index, line in enumerate(text_lines) if contains_bbox(frame, _bbox(line))]
        candidates.append({"bbox": frame, "caption": caption, "source_text_lines": source_lines})
    # A caption pointing at multiple frames is not a safe automatic crop.
    accepted = []
    for candidate in candidates:
        if sum(other["caption"] == candidate["caption"] for other in candidates) == 1:
            accepted.append(candidate)
        elif diagnostics is not None:
            diagnostics.append({"reason": "ambiguous_caption_frames", "bbox": candidate["bbox"],
                                "caption_text": candidate["caption"]["text"]})
    return accepted
