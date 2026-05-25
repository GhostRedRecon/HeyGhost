from __future__ import annotations


def explain_result(llm, result_text: str, max_words: int = 55) -> str:
    cleaned = " ".join((result_text or "").split())
    if not cleaned:
        return "I do not have a previous local result to explain."
    if llm is None:
        return _deterministic_explanation(cleaned, max_words)

    prompt = (
        "Explain this local command or skill result for voice. "
        "Use only the supplied result text. Do not infer missing system facts. "
        f"Keep it under {max_words} words."
    )
    try:
        return llm.generate(prompt, cleaned[:4000], "")
    except Exception:
        return _deterministic_explanation(cleaned, max_words)


def _deterministic_explanation(text: str, max_words: int) -> str:
    words = text.split()
    short = " ".join(words[:max_words])
    if len(words) > max_words:
        short = short.rstrip(" ,.;:") + "."
    return f"The previous result said: {short}"
