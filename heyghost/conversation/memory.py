from __future__ import annotations

import sqlite3
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List


class ConversationMemory:
    def __init__(
        self,
        keep_last_turns: int,
        storage_path: str | None = None,
        summary_max_chars: int = 1200,
        max_persistent_messages: int = 200,
    ) -> None:
        self._turns: Deque[Dict[str, str]] = deque(maxlen=keep_last_turns * 2)
        self.storage_path = storage_path
        self.summary_max_chars = summary_max_chars
        self.max_persistent_messages = max_persistent_messages
        if self.storage_path:
            self._init_store()
            self._load_recent()

    def add_user(self, content: str) -> None:
        self._add("user", content)

    def add_assistant(self, content: str) -> None:
        self._add("assistant", content)

    def as_prompt_text(self) -> str:
        lines = []
        for turn in self._turns:
            role = "User" if turn["role"] == "user" else "Assistant"
            lines.append(f"{role}: {turn['content']}")
        return "\n".join(lines)

    def as_summary_text(self) -> str:
        if not self.storage_path:
            return ""
        rows = self._fetch_recent(self.max_persistent_messages)
        if not rows:
            return ""
        lines = []
        total_chars = 0
        for turn in rows:
            role = "User" if turn["role"] == "user" else "Assistant"
            line = f"{role}: {turn['content']}"
            total_chars += len(line)
            if total_chars > self.summary_max_chars:
                break
            lines.append(line)
        return "\n".join(lines)

    def clear(self) -> None:
        self._turns.clear()
        if self.storage_path:
            with self._connect() as conn:
                conn.execute("DELETE FROM messages")

    def snapshot(self) -> List[Dict[str, str]]:
        return list(self._turns)

    def _add(self, role: str, content: str) -> None:
        content = content.strip()
        if not content:
            return
        item = {"role": role, "content": content}
        self._turns.append(item)
        if self.storage_path:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO messages(role, content) VALUES (?, ?)",
                    (role, content),
                )
                self._trim_store(conn)

    def _connect(self) -> sqlite3.Connection:
        if not self.storage_path:
            raise RuntimeError("Conversation memory storage is not configured")
        return sqlite3.connect(self.storage_path)

    def _init_store(self) -> None:
        if not self.storage_path:
            return
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _load_recent(self) -> None:
        for item in self._fetch_recent(self._turns.maxlen or 0):
            self._turns.append(item)

    def _fetch_recent(self, limit: int) -> list[dict[str, str]]:
        if not self.storage_path or limit <= 0:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM messages
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {"role": role, "content": content}
            for role, content in reversed(rows)
        ]

    def _trim_store(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            DELETE FROM messages
            WHERE id NOT IN (
                SELECT id FROM messages ORDER BY id DESC LIMIT ?
            )
            """,
            (self.max_persistent_messages,),
        )
