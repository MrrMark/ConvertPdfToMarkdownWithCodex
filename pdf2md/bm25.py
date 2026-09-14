"""Deterministic, dependency-free Unicode BM25 retrieval for local evaluation."""

from collections import Counter
import math
import re
import unicodedata

WORD = re.compile(r"\w+(?:[.:/-]\w+)*", re.UNICODE)
HANGUL = re.compile(r"[가-힣]+")


def tokenize(text: str) -> list[str]:
    """Keep Unicode words and technical identifiers; add Hangul syllable bigrams."""
    normalized = unicodedata.normalize("NFC", text).casefold()
    terms = ["word:" + match.group() for match in WORD.finditer(normalized)]
    for match in HANGUL.finditer(normalized):
        word = match.group()
        terms.extend("ko2:" + word[i:i + 2] for i in range(len(word) - 1))
    return terms


class BM25Index:
    """Index chunk text using positive log-IDF BM25 with k1=1.2 and b=0.75."""

    def __init__(self, chunks: list[dict], *, k1: float = 1.2, b: float = 0.75):
        if not math.isfinite(k1) or k1 <= 0 or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("Invalid BM25 parameters")
        ids = [chunk.get("chunk_id") for chunk in chunks]
        if any(not isinstance(key, str) or not key for key in ids) or len(set(ids)) != len(ids):
            raise ValueError("Chunks require unique nonempty chunk_id values")
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.terms = [Counter(tokenize(str(chunk.get("embedding_text") or chunk.get("text") or "")))
                      for chunk in chunks]
        self.lengths = [sum(terms.values()) for terms in self.terms]
        self.average = sum(self.lengths) / len(chunks) if chunks else 0
        self.df = Counter(term for terms in self.terms for term in terms)

    def retrieve(self, query: str, *, top_k: int = 5) -> list[dict]:
        """Return positive-score matches, breaking ties by stable chunk ID."""
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_terms = sorted(set(tokenize(query)))
        scored = []
        for chunk, terms, length in zip(self.chunks, self.terms, self.lengths):
            score = 0.0
            for term in query_terms:
                frequency = terms[term]
                if not frequency:
                    continue
                idf = math.log1p((len(self.chunks) - self.df[term] + 0.5) / (self.df[term] + 0.5))
                norm = 1 - self.b + self.b * length / self.average
                score += idf * frequency * (self.k1 + 1) / (frequency + self.k1 * norm)
            if score > 0:
                scored.append((score, chunk["chunk_id"], chunk))
        scored.sort(key=lambda row: (-row[0], row[1]))
        return [chunk | {"score": score} for score, _, chunk in scored[:top_k]]
