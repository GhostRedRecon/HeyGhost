from __future__ import annotations

import json
from collections.abc import Iterator
from urllib import request


class OllamaClient:
    def __init__(
        self,
        url: str,
        model: str,
        num_ctx: int,
        num_predict: int,
        temperature: float,
        max_response_words: int,
        keep_alive: str = "10m",
    ) -> None:
        self.url = url
        self.model = model
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.temperature = temperature
        self.max_response_words = max_response_words
        self.keep_alive = keep_alive

    def generate(self, system_prompt: str, user_text: str, memory_text: str) -> str:
        text = "".join(self.generate_stream(system_prompt, user_text, memory_text))
        return self._truncate_words(text.strip())

    def generate_stream(
        self,
        system_prompt: str,
        user_text: str,
        memory_text: str,
    ) -> Iterator[str]:
        prompt = (
            f"{system_prompt}\n\n"
            f"Recent conversation:\n{memory_text or '(none)'}\n\n"
            f"User: {user_text}\n"
            "Ghost:"
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=90) as response:
            for line in response:
                if not line.strip():
                    continue
                raw = json.loads(line.decode("utf-8"))
                chunk = raw.get("response", "")
                if chunk:
                    yield chunk

    def _truncate_words(self, text: str) -> str:
        words = text.split()
        if len(words) <= self.max_response_words:
            return text
        return " ".join(words[: self.max_response_words]).rstrip(" ,.;:") + "."
