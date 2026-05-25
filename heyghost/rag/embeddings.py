from __future__ import annotations

import json
from urllib import request


class OllamaEmbedder:
    def __init__(self, generate_url: str, model: str) -> None:
        self.url = generate_url.replace("/api/generate", "/api/embeddings")
        self.model = model

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.model, "prompt": text}
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=60) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        embedding = parsed.get("embedding")
        if not isinstance(embedding, list) or not all(isinstance(item, int | float) for item in embedding):
            raise ValueError("Ollama embedding response did not contain an embedding")
        return [float(item) for item in embedding]
