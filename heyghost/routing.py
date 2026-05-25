from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from heyghost.llm.structured import classify_request
from heyghost.skills.result import SkillResult, unhandled


@dataclass(frozen=True)
class RouteDecision:
    handled: bool
    confidence: float
    route: str
    spoken_text: str = ""
    requires_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class TurnRouter:
    def __init__(
        self,
        skill_registry,
        llm=None,
        structured_routing_enabled: bool = False,
        min_confidence: float = 0.50,
    ) -> None:
        self.skill_registry = skill_registry
        self.llm = llm
        self.structured_routing_enabled = structured_routing_enabled
        self.min_confidence = min_confidence

    def route(self, text: str) -> RouteDecision:
        skill_result = self.skill_registry.maybe_handle(text)
        if skill_result is not None and getattr(skill_result, "handled", True):
            return self._from_skill_result(skill_result)

        if self.structured_routing_enabled and self.llm is not None:
            decision = self._classify_with_ollama(text)
            if decision is not None and decision.confidence >= self.min_confidence:
                return decision

        return RouteDecision(
            handled=False,
            confidence=0.0,
            route="ollama_fallback",
        )

    def _from_skill_result(self, result: SkillResult) -> RouteDecision:
        return RouteDecision(
            handled=result.handled,
            confidence=result.confidence,
            route=result.source,
            spoken_text=result.spoken_text,
            requires_confirmation=result.requires_confirmation,
            metadata=result.metadata,
        )

    def _classify_with_ollama(self, text: str) -> RouteDecision | None:
        decision = classify_request(self.llm, text)
        if decision is None:
            return None
        return RouteDecision(
            handled=False,
            confidence=decision.confidence,
            route=f"classifier:{decision.route}",
            metadata={
                "domain": decision.domain,
                "reason": decision.reason,
            },
        )


__all__ = ["RouteDecision", "TurnRouter", "unhandled"]
