from tempfile import TemporaryDirectory

from heyghost.rag.rag_skill import LocalRAG, NO_LOCAL_KNOWLEDGE
from heyghost.rag.vector_store import SQLiteVectorStore


def test_rag_requires_source_for_factual_answer():
    with TemporaryDirectory() as tmp:
        rag = LocalRAG(
            store=SQLiteVectorStore(f"{tmp}/rag.sqlite3"),
            embedder=None,
            knowledge_dir=f"{tmp}/knowledge",
            require_sources=True,
        )
        answer = rag.answer("USB microphone")
        assert answer.text == NO_LOCAL_KNOWLEDGE
        assert answer.sources == []
