"""A small keyword-based retriever over the local GST rule files (the "R" in RAG).

How it works:
1. At startup every .txt file in data/gst_rules/ is split into chunks (one chunk per
   paragraph; each paragraph starts with a title line).
2. A query is turned into keywords (lowercase words, minus common stop words).
3. Each chunk is scored by the keywords it shares with the query. Rare words count
   more than common ones (IDF weighting), so "igst" matters more than "invoice".
4. The top-scoring chunks, with their file names, are handed to Gemini as context.

With only a handful of rule files, keyword matching is enough. Embeddings and a
vector database would be the upgrade path for a much larger knowledge base.
"""
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import BASE_DIR

RULES_DIR = BASE_DIR / "data" / "gst_rules"

STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "by", "is", "are", "be",
    "must", "with", "as", "at", "it", "its", "this", "that", "from", "not", "if", "can",
    "has", "have", "was", "were", "which", "when", "than", "also", "any", "all", "per",
    "rs", "such", "other", "their", "there", "these", "those", "does", "should", "only",
}


@dataclass
class RuleChunk:
    source: str   # file name, e.g. "gst_invoice_rules.txt"
    title: str    # first line of the paragraph
    text: str
    score: float = 0.0


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


class GSTRuleRetriever:
    def __init__(self, rules_dir: Path = RULES_DIR):
        self.chunks: list[RuleChunk] = []
        for path in sorted(rules_dir.glob("*.txt")):
            for paragraph in path.read_text(encoding="utf-8").split("\n\n"):
                paragraph = paragraph.strip()
                if paragraph:
                    title = paragraph.split("\n", 1)[0]
                    self.chunks.append(RuleChunk(source=path.name, title=title, text=paragraph))

        self._chunk_tokens = [tokenize(c.text) for c in self.chunks]
        # IDF: words found in fewer chunks get a higher weight
        doc_freq: dict[str, int] = {}
        for tokens in self._chunk_tokens:
            for token in tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1
        n = len(self.chunks)
        self._idf = {t: math.log((n + 1) / (df + 1)) + 1 for t, df in doc_freq.items()}

    def retrieve(self, query: str, top_k: int = 5) -> list[RuleChunk]:
        query_tokens = tokenize(query)
        scored = []
        for chunk, tokens in zip(self.chunks, self._chunk_tokens):
            score = sum(self._idf[t] for t in query_tokens & tokens)
            if score > 0:
                scored.append(RuleChunk(chunk.source, chunk.title, chunk.text, round(score, 2)))
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]


@lru_cache
def get_retriever() -> GSTRuleRetriever:
    return GSTRuleRetriever()
