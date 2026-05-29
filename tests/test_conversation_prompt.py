from __future__ import annotations

from heyghost.app import SYSTEM_PROMPT
from heyghost.conversation.memory import ConversationMemory
from heyghost.llm.ollama_client import OllamaClient


def test_system_prompt_avoids_ghost_roleplay() -> None:
    assert "do not roleplay as a ghost" in SYSTEM_PROMPT
    assert "answer the actual question first" in SYSTEM_PROMPT
    assert "Do not use Markdown" in SYSTEM_PROMPT


def test_ollama_prompt_uses_assistant_role_label() -> None:
    llm = OllamaClient(
        url="http://localhost:11434/api/generate",
        model="qwen2.5:0.5b",
        num_ctx=1024,
        num_predict=80,
        temperature=0.2,
        max_response_words=60,
    )

    prompt = llm.build_prompt("System", "What is RAM?", "User: Hi")

    assert prompt.endswith("Assistant:")
    assert "Ghost:" not in prompt


def test_conversation_memory_uses_neutral_assistant_label() -> None:
    memory = ConversationMemory(keep_last_turns=2)
    memory.add_user("What is RAM?")
    memory.add_assistant("RAM is short-term working memory for a computer.")

    prompt_text = memory.as_prompt_text()

    assert "Assistant: RAM is short-term working memory for a computer." in prompt_text
    assert "Ghost:" not in prompt_text


def test_ollama_truncation_prefers_sentence_boundary() -> None:
    llm = OllamaClient(
        url="http://localhost:11434/api/generate",
        model="qwen2.5:0.5b",
        num_ctx=1024,
        num_predict=64,
        temperature=0.2,
        max_response_words=10,
    )

    text = (
        "RAM is short-term working memory for your computer. "
        "It matters because apps use it to stay responsive while you work."
    )

    assert llm._truncate_words(text) == "RAM is short-term working memory for your computer."
