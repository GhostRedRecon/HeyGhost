from __future__ import annotations

from dataclasses import dataclass

from heyghost.llm.log_analyzer import analyze_debug_log
from heyghost.llm.note_summarizer import action_items, shorten_text, summarize_note
from heyghost.llm.result_explainer import explain_result
from heyghost.llm.structured import classify_request


@dataclass
class LLMCapabilityLayer:
    llm: object | None
    debug_events_file: str
    max_spoken_words: int = 55
    vision_enabled: bool = False

    def overview(self) -> str:
        parts = [
            "classify requests",
            "summarize notes",
            "explain command results",
            "search local knowledge",
            "analyze my logs",
            "teach topics briefly",
            "suggest config changes",
        ]
        if self.vision_enabled:
            parts.append("describe images with a local vision model")
        return "I can " + ", ".join(parts[:-1]) + f", and {parts[-1]}."

    def classify(self, text: str) -> str:
        target = _after_any(text, ("classify this request", "classify request"))
        if not target:
            return "Say classify this request, then the request you want classified."
        decision = classify_request(self.llm, target) if self.llm is not None else None
        if decision is None:
            return "I could not validate the model classification, so I would fall back to deterministic routing."
        return f"I classify that as {decision.route}, domain {decision.domain}, confidence {decision.confidence:.2f}."

    def explain(self, previous_result: str) -> str:
        return explain_result(self.llm, previous_result, self.max_spoken_words)

    def summarize_note(self, text: str) -> str:
        note = _after_any(text, ("summarize this note", "summarize note"))
        return summarize_note(self.llm, note, self.max_spoken_words)

    def shorten(self, text: str, previous_result: str) -> str:
        target = _after_any(text, ("make that shorter", "make this shorter"))
        if not target:
            target = previous_result
        return shorten_text(self.llm, target, min(35, self.max_spoken_words))

    def action_items(self, text: str) -> str:
        note = _after_any(text, ("turn this into action items", "action items"))
        return action_items(self.llm, note, self.max_spoken_words)

    def analyze_logs(self) -> str:
        return analyze_debug_log(self.llm, self.debug_events_file)

    def teach_linux_networking(self) -> str:
        if self.llm is None:
            return (
                "Linux networking connects interfaces, addresses, routes, DNS, and firewalls. "
                "Start with ip addr, ip route, resolvectl, ping, and ss to inspect each layer."
            )
        prompt = (
            "Teach Linux networking briefly for a voice assistant. Keep it practical, defensive, "
            "and under the word limit. Do not claim current system state."
        )
        try:
            return self.llm.generate(prompt, "Teach me about Linux networking.", "")
        except Exception:
            return (
                "Linux networking connects interfaces, addresses, routes, DNS, and firewalls. "
                "Start by learning what each layer does before changing settings."
            )

    def suggest_config(self, text: str) -> str:
        context = _after_any(text, ("suggest a config change", "config suggestion"))
        if self.llm is None:
            return "For safer voice responses, keep max spoken words low and structured outputs enabled."
        prompt = (
            "Suggest one safe HeyGhost config change. Do not modify files. "
            "Mention that the user must review and confirm before any change. "
            "Do not invent current config values unless supplied."
        )
        try:
            return self.llm.generate(prompt, context or "Suggest a safe config change.", "")
        except Exception:
            return "Keep responses short and review any config change before applying it."


def _after_any(text: str, prefixes: tuple[str, ...]) -> str:
    lowered = text.lower()
    for prefix in prefixes:
        index = lowered.find(prefix)
        if index != -1:
            return text[index + len(prefix) :].strip(" :,-")
    return ""
