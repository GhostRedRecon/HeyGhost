from __future__ import annotations

from dataclasses import dataclass

from heyghost.rag.chunker import chunk_text
from heyghost.rag.document_loader import load_documents
from heyghost.rag.embeddings import OllamaEmbedder
from heyghost.rag.vector_store import SQLiteVectorStore, SearchHit


NO_LOCAL_KNOWLEDGE = "I do not have that in my local knowledge."


@dataclass
class RAGAnswer:
    text: str
    sources: list[str]


class LocalRAG:
    def __init__(
        self,
        store: SQLiteVectorStore,
        embedder: OllamaEmbedder | None,
        knowledge_dir: str,
        chunk_chars: int = 800,
        chunk_overlap: int = 120,
        top_k: int = 4,
        require_sources: bool = True,
        llm=None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.knowledge_dir = knowledge_dir
        self.chunk_chars = chunk_chars
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.require_sources = require_sources
        self.llm = llm

    def index(self) -> int:
        chunks = []
        for document in load_documents(self.knowledge_dir):
            chunks.extend(
                chunk_text(document.source_name, document.text, self.chunk_chars, self.chunk_overlap)
            )
        embedded = []
        if self.embedder is None:
            self.store.replace([(chunk, []) for chunk in chunks])
            return len(chunks)
        for chunk in chunks:
            embedded.append((chunk, self.embedder.embed(chunk.text)))
        self.store.replace(embedded)
        return len(embedded)

    def answer(self, query: str) -> RAGAnswer:
        hits = self.search(query)
        if self.require_sources and not hits:
            return RAGAnswer(NO_LOCAL_KNOWLEDGE, [])
        sources = sorted({hit.source for hit in hits})
        if not hits:
            return RAGAnswer(NO_LOCAL_KNOWLEDGE, [])
        if self.llm is None:
            return RAGAnswer(_extractive_answer(hits, sources), sources)
        context = "\n\n".join(f"Source: {hit.source}\n{hit.text}" for hit in hits)
        prompt = (
            "Answer the question using only the local source excerpts. "
            "If the excerpts do not answer it, say exactly: "
            f"{NO_LOCAL_KNOWLEDGE} Include source file names at the end."
        )
        try:
            text = self.llm.generate(prompt, f"Question: {query}\n\n{context}", "")
        except Exception:
            text = _extractive_answer(hits, sources)
        if self.require_sources and not sources:
            text = NO_LOCAL_KNOWLEDGE
        elif sources and not any(source in text for source in sources):
            text = f"{text} Sources: {', '.join(sources)}."
        return RAGAnswer(text, sources)

    def search(self, query: str) -> list[SearchHit]:
        if self.embedder is not None:
            try:
                hits = self.store.search(self.embedder.embed(query), self.top_k)
                if hits:
                    return hits
            except Exception:
                pass
        return self.store.lexical_search(query, self.top_k)


def _extractive_answer(hits: list[SearchHit], sources: list[str]) -> str:
    first = hits[0].text.strip().split(".")[0].strip()
    if not first:
        return NO_LOCAL_KNOWLEDGE
    return f"{first}. Sources: {', '.join(sources)}."
