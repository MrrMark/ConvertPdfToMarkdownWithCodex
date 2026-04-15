from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pdf2md.extractors.images import StructureOcrCandidate, _resolve_structure_marker_recovery, extract_images
from pdf2md.models import ImageMode
from pdf2md.utils.structure import is_caption_candidate


class _FakePdfPlumberPage:
    def __init__(self, *, images: list[dict], text_lines: list[dict]) -> None:
        self.images = images
        self._text_lines = text_lines

    def extract_text_lines(self) -> list[dict]:
        return self._text_lines


class _FakePdfPlumberDocument:
    def __init__(self, pages: list[_FakePdfPlumberPage]) -> None:
        self.pages = pages

    def __enter__(self) -> _FakePdfPlumberDocument:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeImage:
    def __init__(self, data: bytes, name: str = "figure.png", width: int = 120, height: int = 80) -> None:
        self.data = data
        self.name = name
        self.indirect_reference = {"/Width": width, "/Height": height}


def _fake_reader(image: _FakeImage) -> SimpleNamespace:
    return SimpleNamespace(pages=[SimpleNamespace(images=[image])])


def test_extract_images_does_not_write_files_for_embedded_or_placeholder(
    monkeypatch,
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    fake_page = _FakePdfPlumberPage(
        images=[{"top": 100.0, "bottom": 180.0, "x0": 50.0, "x1": 170.0, "width": 120, "height": 80}],
        text_lines=[{"top": 182.0, "text": "Figure 1: Sample image"}],
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images.pdfplumber.open",
        lambda *args, **kwargs: _FakePdfPlumberDocument([fake_page]),
    )

    for mode in (ImageMode.EMBEDDED, ImageMode.PLACEHOLDER):
        output_dir = tmp_path / mode.value
        result = extract_images(
            reader=_fake_reader(_FakeImage(b"image-bytes")),
            pdf_path=sample_pdf,
            selected_pages=[1],
            password=None,
            output_dir=output_dir,
            image_mode=mode,
        )
        files = list((output_dir / "assets" / "images").glob("*"))
        assert files == []
        assert result.assets[0].caption_text == "Figure 1: Sample image"
        assert result.assets[0].caption_source == "nearby_caption"


def test_extract_images_writes_referenced_file(monkeypatch, sample_pdf: Path, tmp_path: Path) -> None:
    fake_page = _FakePdfPlumberPage(
        images=[{"top": 100.0, "bottom": 180.0, "x0": 50.0, "x1": 170.0, "width": 120, "height": 80}],
        text_lines=[],
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images.pdfplumber.open",
        lambda *args, **kwargs: _FakePdfPlumberDocument([fake_page]),
    )

    output_dir = tmp_path / "referenced"
    result = extract_images(
        reader=_fake_reader(_FakeImage(b"image-bytes")),
        pdf_path=sample_pdf,
        selected_pages=[1],
        password=None,
        output_dir=output_dir,
        image_mode=ImageMode.REFERENCED,
    )

    files = list((output_dir / "assets" / "images").glob("*"))
    assert len(files) == 1
    assert result.assets[0].alt_text == "Image page-0001-figure-001"


def test_caption_candidate_requires_caption_line_prefix() -> None:
    assert is_caption_candidate("Figure 1: Sample image") is True
    assert is_caption_candidate("This specification defines Figure 2 behavior") is False


def test_structure_marker_recovery_prefers_exact_candidate() -> None:
    decision = _resolve_structure_marker_recovery(
        [
            StructureOcrCandidate(text="2.2.1", confidence=97.0, votes=4),
            StructureOcrCandidate(text="22.1", confidence=98.0, votes=2),
        ],
        parent_heading_index="2.2",
        child_heading_index=None,
    )

    assert decision.text == "2.2.1"
    assert decision.reason == "STRUCTURE_MARKER_RECOVERED_EXACT"
    assert decision.recovery_strategy == "ocr_exact"
    assert decision.context_validated is False


def test_structure_marker_recovery_context_validates_missing_dot() -> None:
    decision = _resolve_structure_marker_recovery(
        [
            StructureOcrCandidate(text="22.1", confidence=95.0, votes=5),
            StructureOcrCandidate(text="221", confidence=93.0, votes=2),
        ],
        parent_heading_index="2.2",
        child_heading_index=None,
    )

    assert decision.text == "2.2.1"
    assert decision.reason == "STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED"
    assert decision.recovery_strategy == "parent_heading_context"
    assert decision.context_validated is True


def test_structure_marker_recovery_rejects_ambiguous_context_guess() -> None:
    decision = _resolve_structure_marker_recovery(
        [
            StructureOcrCandidate(text="22.1", confidence=95.0, votes=3),
            StructureOcrCandidate(text="22.2", confidence=95.0, votes=3),
        ],
        parent_heading_index="2.2",
        child_heading_index=None,
    )

    assert decision.text is None
    assert decision.reason == "STRUCTURE_MARKER_SUPPRESSED_AMBIGUOUS"


def test_structure_marker_recovery_uses_child_heading_context() -> None:
    decision = _resolve_structure_marker_recovery(
        [
            StructureOcrCandidate(text="324", confidence=77.5, votes=24),
            StructureOcrCandidate(text="32.4", confidence=73.25, votes=8),
            StructureOcrCandidate(text="3.2.4", confidence=85.67, votes=6),
        ],
        parent_heading_index=None,
        child_heading_index="3.2.4.1",
    )

    assert decision.text == "3.2.4"
    assert decision.reason == "STRUCTURE_MARKER_RECOVERED_EXACT"


def test_structure_marker_recovery_uses_ancestor_parent_context() -> None:
    decision = _resolve_structure_marker_recovery(
        [
            StructureOcrCandidate(text="41.6", confidence=90.68, votes=44),
            StructureOcrCandidate(text="416", confidence=76.0, votes=4),
        ],
        parent_heading_index="4.1.5.2",
        child_heading_index=None,
    )

    assert decision.text == "4.1.6"
    assert decision.reason == "STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED"
    assert decision.recovery_strategy == "parent_heading_context"


def test_structure_marker_recovery_uses_sibling_sequence_context() -> None:
    decision = _resolve_structure_marker_recovery(
        [
            StructureOcrCandidate(text="214", confidence=88.1, votes=40),
            StructureOcrCandidate(text="2714", confidence=76.0, votes=6),
            StructureOcrCandidate(text="2.14", confidence=83.0, votes=2),
        ],
        parent_heading_index=None,
        child_heading_index=None,
        previous_recovered_text="2.1.3",
        next_recovered_text="2.1.5",
    )

    assert decision.text == "2.1.4"
    assert decision.reason == "STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED"
    assert decision.recovery_strategy == "sibling_sequence_context"


def test_structure_marker_recovery_uses_previous_sibling_context() -> None:
    decision = _resolve_structure_marker_recovery(
        [
            StructureOcrCandidate(text="417", confidence=72.08, votes=48),
        ],
        parent_heading_index=None,
        child_heading_index=None,
        previous_recovered_text="4.1.6",
        next_recovered_text=None,
    )

    assert decision.text == "4.1.7"
    assert decision.reason == "STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED"
    assert decision.recovery_strategy == "previous_sibling_context"


def test_extract_images_suppresses_structure_marker_and_recovers_text(monkeypatch, sample_pdf: Path, tmp_path: Path) -> None:
    fake_page = _FakePdfPlumberPage(
        images=[{"top": 260.0, "bottom": 268.0, "x0": 72.0, "x1": 92.0, "width": 20, "height": 7}],
        text_lines=[
            {"top": 242.0, "x0": 72.0, "text": "2.2 I/O Controller Requirements"},
            {"top": 262.0, "x0": 108.0, "text": "Command Support"},
        ],
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images.pdfplumber.open",
        lambda *args, **kwargs: _FakePdfPlumberDocument([fake_page]),
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images._collect_structure_marker_candidates",
        lambda data: [StructureOcrCandidate(text="2.2.1", confidence=98.0, votes=4)],
    )

    result = extract_images(
        reader=_fake_reader(_FakeImage(b"image-bytes", name="structure.png", width=20, height=7)),
        pdf_path=sample_pdf,
        selected_pages=[1],
        password=None,
        output_dir=tmp_path / "structure-marker",
        image_mode=ImageMode.REFERENCED,
    )

    assert result.assets == []
    assert result.blocks_by_page == {}
    assert result.excluded_assets[0].reason == "STRUCTURE_MARKER_RECOVERED_EXACT"
    assert result.excluded_assets[0].classification == "STRUCTURE_MARKER"
    assert result.excluded_assets[0].recovered_text == "2.2.1"
    assert result.excluded_assets[0].recovery_strategy == "ocr_exact"
    assert result.excluded_assets[0].parent_heading_index == "2.2"
    assert result.structure_recoveries[0]["title_text"] == "Command Support"
    assert result.structure_recoveries[0]["recovered_text"] == "2.2.1"


def test_extract_images_suppresses_structure_marker_without_hallucinating(monkeypatch, sample_pdf: Path, tmp_path: Path) -> None:
    fake_page = _FakePdfPlumberPage(
        images=[{"top": 260.0, "bottom": 268.0, "x0": 72.0, "x1": 92.0, "width": 20, "height": 7}],
        text_lines=[
            {"top": 242.0, "x0": 72.0, "text": "2.2 I/O Controller Requirements"},
            {"top": 262.0, "x0": 108.0, "text": "Command Support"},
        ],
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images.pdfplumber.open",
        lambda *args, **kwargs: _FakePdfPlumberDocument([fake_page]),
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images._collect_structure_marker_candidates",
        lambda data: [],
    )

    result = extract_images(
        reader=_fake_reader(_FakeImage(b"image-bytes", name="structure.png", width=20, height=7)),
        pdf_path=sample_pdf,
        selected_pages=[1],
        password=None,
        output_dir=tmp_path / "structure-marker-suppressed",
        image_mode=ImageMode.REFERENCED,
    )

    assert result.assets == []
    assert result.blocks_by_page == {}
    assert result.excluded_assets[0].reason == "STRUCTURE_MARKER_SUPPRESSED_NO_CANDIDATE"
    assert result.excluded_assets[0].recovered_text is None
    assert result.structure_recoveries == []
