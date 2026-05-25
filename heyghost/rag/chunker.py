from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    source: str
    text: str
    chunk_index: int


def chunk_text(source: str, text: str, chunk_chars: int = 800, overlap: int = 120) -> list[TextChunk]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []
    chunk_chars = max(200, chunk_chars)
    overlap = max(0, min(overlap, chunk_chars // 2))
    chunks = []
    start = 0
    index = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_chars)
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start + chunk_chars // 2:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(TextChunk(source=source, text=chunk, chunk_index=index))
            index += 1
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks
