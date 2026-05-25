from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from heyghost.rag.chunker import TextChunk


@dataclass(frozen=True)
class SearchHit:
    source: str
    text: str
    score: float


class SQLiteVectorStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                create table if not exists chunks (
                    id integer primary key,
                    source text not null,
                    chunk_index integer not null,
                    text text not null,
                    embedding text not null
                )
                """
            )
            conn.execute("create index if not exists idx_chunks_source on chunks(source)")

    def replace(self, chunks: list[tuple[TextChunk, list[float]]]) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.execute("delete from chunks")
            conn.executemany(
                "insert into chunks(source, chunk_index, text, embedding) values (?, ?, ?, ?)",
                [
                    (chunk.source, chunk.chunk_index, chunk.text, json.dumps(embedding))
                    for chunk, embedding in chunks
                ],
            )

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[SearchHit]:
        self.initialize()
        hits = []
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute("select source, text, embedding from chunks").fetchall()
        for source, text, raw_embedding in rows:
            try:
                embedding = json.loads(raw_embedding)
            except json.JSONDecodeError:
                continue
            if not isinstance(embedding, list):
                continue
            score = _cosine(query_embedding, [float(item) for item in embedding])
            hits.append(SearchHit(source=source, text=text, score=score))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    def lexical_search(self, query: str, top_k: int = 4) -> list[SearchHit]:
        self.initialize()
        terms = {term for term in query.lower().split() if len(term) > 2}
        if not terms:
            return []
        hits = []
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute("select source, text from chunks").fetchall()
        for source, text in rows:
            lowered = text.lower()
            score = sum(1 for term in terms if term in lowered) / max(len(terms), 1)
            if score > 0:
                hits.append(SearchHit(source=source, text=text, score=score))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
