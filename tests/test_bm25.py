"""Regression tests for Korean retrieval and source-aware evaluation."""

import math
import unicodedata

import pytest

from pdf2md.bm25 import BM25Index, tokenize
from scripts.run_bm25_eval import evaluate, has_bbox


def test_unicode_identifier_and_hangul_normalization():
    text = "제어기는 MSIXCAP.MXC.TS 07:04 1_0000h를 확인한다"
    assert tokenize(text) == tokenize(unicodedata.normalize("NFD", text))
    assert {"word:msixcap.mxc.ts", "word:07:04", "ko2:제어", "ko2:어기"} <= set(tokenize(text))


def test_korean_inflection_matches_without_latin_words():
    chunks = [{"chunk_id": "a", "text": "제어기는 준비 상태를 확인한다"},
              {"chunk_id": "b", "text": "메모리 주소와 길이"}]
    assert BM25Index(chunks).retrieve("제어기의 상태")[0]["chunk_id"] == "a"


def test_bm25_reference_score_and_tie_order():
    chunks = [{"chunk_id": "z", "text": "alpha"}, {"chunk_id": "a", "text": "alpha"}]
    result = BM25Index(chunks).retrieve("alpha alpha")
    assert result[0]["score"] == pytest.approx(math.log1p(0.5 / 2.5))
    assert [r["chunk_id"] for r in result] == ["a", "z"]
    assert BM25Index(list(reversed(chunks))).retrieve("alpha") == result


def test_frequency_saturates_and_empty_documents_are_safe():
    index = BM25Index([{"chunk_id": "a", "text": "alpha " * 100}, {"chunk_id": "b", "text": ""}])
    assert 0 < index.retrieve("alpha")[0]["score"] < math.log(2) * 2.2
    assert index.retrieve("없는단어") == []
    assert BM25Index([]).retrieve("alpha") == []
    with pytest.raises(ValueError):
        index.retrieve("alpha", top_k=0)


def dataset():
    return {"review": {"status": "draft"}, "queries": [{
        "query_id": f"{language}-{i}", "language": language, "query": "alpha",
        "expected_refs": [{"source_type": "requirement", "source_id": key, "page": 1} for key in ("r1", "r2")],
        "critical_tokens": ["0h"],
    } for language in ("ko", "en") for i in range(15)]}


def test_recall_is_not_hit_rate_and_unrelated_tokens_do_not_pass():
    chunks = [{"chunk_id": "a", "text": "alpha", "source_refs": [
        {"source_type": "requirement", "source_id": "r1", "page": 1, "bbox": [0, 0, 1, 1]}]},
        {"chunk_id": "b", "text": "alpha 0h", "source_refs": [
            {"source_type": "figure", "source_id": "r2", "page": 1, "bbox": [0, 0, 1, 1]}]}]
    report = evaluate(chunks, dataset())
    for method in ("bm25", "lexical"):
        metrics = report["metrics"][method]["all"]
        assert metrics["recall_at_5"] == 0.5
        assert metrics["citation_coverage_at_5"] == 0.5
        assert metrics["critical_token_preservation_at_5"] == 0
    assert not report["human_review_complete"]


def test_invalid_bilingual_set_and_duplicate_chunks_fail():
    invalid = dataset()
    invalid["queries"].pop()
    with pytest.raises(ValueError, match="15 Korean"):
        evaluate([], invalid)
    with pytest.raises(ValueError, match="unique"):
        BM25Index([{"chunk_id": "a"}, {"chunk_id": "a"}])


def test_wrong_page_cannot_earn_citation_credit():
    chunks = [{"chunk_id": "a", "text": "alpha 0h", "source_refs": [
        {"source_type": "requirement", "source_id": "r1", "page": 2, "bbox": [0, 0, 1, 1]}]}]
    metrics = evaluate(chunks, dataset())["metrics"]["bm25"]["all"]
    assert metrics["recall_at_5"] == metrics["citation_coverage_at_5"] == 0


def test_citation_requires_finite_nonempty_bbox():
    for bbox in ([0, 0, 0, 1], [0, 0, float("inf"), 1], [0], "bbox"):
        assert not has_bbox({"bbox": bbox})
    assert has_bbox({"bbox": [0, 0, 1, 1]})


def test_critical_token_is_not_a_substring_of_another_identifier():
    chunks = [{"chunk_id": "a", "text": "alpha 10h", "source_refs": [
        {"source_type": "requirement", "source_id": "r1", "page": 1, "bbox": [0, 0, 1, 1]}]}]
    report = evaluate(chunks, dataset())
    for method in ("bm25", "lexical"):
        assert report["metrics"][method]["all"]["critical_token_preservation_at_5"] == 0
