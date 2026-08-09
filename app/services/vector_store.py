"""Replaceable lightweight vector store (TF-IDF)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge_base"


@dataclass
class RetrievedChunk:
    document_id: str
    document_name: str
    chunk_id: str
    text: str
    score: float


class VectorStore:
    """TF-IDF backed retriever with a replaceable interface for Azure AI Search later."""

    def __init__(self, knowledge_dir: Path | None = None):
        self.knowledge_dir = knowledge_dir or KB_DIR
        self.chunks: list[dict[str, Any]] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._build()

    def _chunk_markdown(self, doc_id: str, text: str) -> list[dict[str, Any]]:
        parts = re.split(r"\n(?=#)", text.strip())
        chunks = []
        for idx, part in enumerate(parts):
            cleaned = part.strip()
            if not cleaned:
                continue
            chunks.append(
                {
                    "document_id": doc_id,
                    "document_name": doc_id,
                    "chunk_id": f"{doc_id}::chunk-{idx}",
                    "text": cleaned,
                }
            )
        return chunks

    def _build(self) -> None:
        self.chunks = []
        for path in sorted(self.knowledge_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            self.chunks.extend(self._chunk_markdown(path.name, text))
        corpus = [c["text"] for c in self.chunks]
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform(corpus)

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        assert self._vectorizer is not None and self._matrix is not None
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix).ravel()
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results: list[RetrievedChunk] = []
        for idx, score in ranked:
            chunk = self.chunks[idx]
            results.append(
                RetrievedChunk(
                    document_id=chunk["document_id"],
                    document_name=chunk["document_name"],
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    score=round(float(score), 4),
                )
            )
        return results

    def documents(self) -> list[str]:
        return sorted({c["document_name"] for c in self.chunks})
