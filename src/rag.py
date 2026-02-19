import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict


WORD_RE = re.compile(r"[a-zA-Z0-9_\-\u00C0-\u017F]+")


@dataclass
class Chunk:
    source: str
    text: str


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


class LocalRetriever:
    def __init__(self, docs_dir: str = "docs", chunk_size: int = 700):
        self.docs_dir = Path(docs_dir)
        self.chunk_size = chunk_size
        self.chunks: List[Chunk] = []
        self.df: Dict[str, int] = {}
        self._build_index()

    def _split_text(self, text: str) -> List[str]:
        text = text.strip()
        if not text:
            return []
        parts: List[str] = []
        for i in range(0, len(text), self.chunk_size):
            parts.append(text[i : i + self.chunk_size])
        return parts

    def _build_index(self) -> None:
        self.chunks = []
        self.df = {}

        if not self.docs_dir.exists():
            return

        files = list(self.docs_dir.glob("*.md")) + list(self.docs_dir.glob("*.txt"))
        for file_path in files:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for piece in self._split_text(content):
                self.chunks.append(Chunk(source=file_path.name, text=piece))

        for chunk in self.chunks:
            unique_terms = set(tokenize(chunk.text))
            for term in unique_terms:
                self.df[term] = self.df.get(term, 0) + 1

    def _tfidf_score(self, query_tokens: List[str], chunk: Chunk) -> float:
        chunk_tokens = tokenize(chunk.text)
        if not chunk_tokens:
            return 0.0

        tf: Dict[str, float] = {}
        for token in chunk_tokens:
            tf[token] = tf.get(token, 0.0) + 1.0

        total = float(len(chunk_tokens))
        score = 0.0
        n_chunks = max(1, len(self.chunks))

        for token in query_tokens:
            term_tf = tf.get(token, 0.0) / total
            if term_tf == 0.0:
                continue
            term_df = self.df.get(token, 0)
            idf = math.log((n_chunks + 1) / (term_df + 1)) + 1.0
            score += term_tf * idf
        return score

    def retrieve(self, query: str, top_k: int = 4) -> List[Tuple[Chunk, float]]:
        q_tokens = tokenize(query)
        if not q_tokens or not self.chunks:
            return []

        scored: List[Tuple[Chunk, float]] = []
        for chunk in self.chunks:
            score = self._tfidf_score(q_tokens, chunk)
            if score > 0:
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
