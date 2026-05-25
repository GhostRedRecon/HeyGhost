from __future__ import annotations


SYSTEM_FACT_TERMS = (
    "cpu",
    "memory",
    "ram",
    "disk",
    "storage",
    "operating system",
    "os",
    "system status",
    "model",
    "hardware",
    "ip address",
)


TOOL_RESULT_TERMS = (
    "i checked",
    "i ran",
    "the command output",
    "your system has",
    "your disk has",
)


def needs_trusted_source(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in SYSTEM_FACT_TERMS)


def guard_llm_response(user_text: str, response: str, source: str) -> str:
    if source.startswith("local skill") or source.startswith("knowledge"):
        return response
    if needs_trusted_source(user_text):
        return (
            "I should not guess system status. Please ask for the exact system "
            "info, like memory, CPU, disk space, or current model."
        )
    lowered = response.lower()
    if any(term in lowered for term in TOOL_RESULT_TERMS):
        return (
            "I do not have a verified tool result for that. Please ask a specific "
            "system or desktop skill request."
        )
    return response
