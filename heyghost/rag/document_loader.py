from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SUFFIXES = {".txt", ".md", ".rst", ".log", ".jsonl", ".yaml", ".yml"}


@dataclass(frozen=True)
class LocalDocument:
    path: Path
    text: str

    @property
    def source_name(self) -> str:
        return self.path.name


def load_documents(knowledge_dir: str) -> list[LocalDocument]:
    root = Path(knowledge_dir)
    if not root.exists() or not root.is_dir():
        return []
    documents = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cleaned = text.strip()
        if cleaned:
            documents.append(LocalDocument(path=path, text=cleaned))
    return documents
