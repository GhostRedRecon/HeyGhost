from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


VALID_ROUTES = {"domain", "general", "clarify", "local_skill", "rag", "capability"}
VALID_DOMAINS = {
    "yoga",
    "cybersecurity",
    "linux",
    "system",
    "rag",
    "capabilities",
    "general",
}


@dataclass(frozen=True)
class IntentClassification:
    route: str
    confidence: float
    domain: str
    reason: str


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        raise ValueError("empty structured response")
    if text.startswith("```"):
        text = text.strip("` \n")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("structured response did not contain a JSON object")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("structured response must be a JSON object")
    return parsed


def validate_intent_classification(parsed: dict[str, Any]) -> IntentClassification:
    route = parsed.get("route")
    confidence = parsed.get("confidence")
    domain = parsed.get("domain", "general")
    reason = parsed.get("reason", "")

    if route not in VALID_ROUTES:
        raise ValueError("invalid route")
    if not isinstance(confidence, int | float):
        raise ValueError("confidence must be numeric")
    if not isinstance(domain, str) or domain not in VALID_DOMAINS:
        raise ValueError("invalid domain")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")

    return IntentClassification(
        route=route,
        confidence=max(0.0, min(float(confidence), 1.0)),
        domain=domain,
        reason=reason[:120],
    )


def classify_request(llm, text: str) -> IntentClassification | None:
    prompt = (
        "You classify one local voice assistant turn. Return JSON only. "
        'Schema: {"route":"domain|general|clarify|local_skill|rag|capability",'
        '"confidence":0.0,"domain":"yoga|cybersecurity|linux|system|rag|'
        'capabilities|general","reason":"short"}. '
        "Do not answer the user. Do not propose shell commands."
    )
    try:
        raw = llm.generate(prompt, text, "")
        return validate_intent_classification(parse_json_object(raw))
    except Exception:
        return None
