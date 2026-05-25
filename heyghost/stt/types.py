from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float = 1.0
    engine: str = "unknown"
