from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillResult:
    handled: bool
    confidence: float
    spoken_text: str
    source: str
    requires_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.source

    @property
    def text(self) -> str:
        return self.spoken_text


def unhandled(source: str = "unhandled") -> SkillResult:
    return SkillResult(
        handled=False,
        confidence=0.0,
        spoken_text="",
        source=source,
    )
