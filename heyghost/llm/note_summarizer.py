from __future__ import annotations


def summarize_note(llm, note_text: str, max_words: int = 55) -> str:
    cleaned = " ".join((note_text or "").split())
    if not cleaned:
        return "Start with summarize this note, then say the note you want summarized."
    if llm is None:
        return _fallback_summary(cleaned, max_words)

    prompt = (
        "Summarize this voice note and include action items if any are explicit. "
        "Use only the note text. Do not add facts. "
        f"Keep the spoken response under {max_words} words."
    )
    try:
        return llm.generate(prompt, cleaned[:6000], "")
    except Exception:
        return _fallback_summary(cleaned, max_words)


def action_items(llm, note_text: str, max_words: int = 55) -> str:
    cleaned = " ".join((note_text or "").split())
    if not cleaned:
        return "Say the note after the request, and I will pull out action items."
    if llm is None:
        return "I found no explicit action items." if " need to " not in cleaned.lower() else _fallback_summary(cleaned, max_words)
    prompt = (
        "Extract explicit action items from this note for voice. "
        "If none are explicit, say there are no explicit action items. "
        f"Keep it under {max_words} words."
    )
    try:
        return llm.generate(prompt, cleaned[:6000], "")
    except Exception:
        return _fallback_summary(cleaned, max_words)


def shorten_text(llm, text: str, max_words: int = 35) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return "Say what you want shortened after make that shorter."
    if llm is None:
        return _fallback_summary(cleaned, max_words)
    prompt = f"Make this text shorter for speech. Use only the text. Keep it under {max_words} words."
    try:
        return llm.generate(prompt, cleaned[:4000], "")
    except Exception:
        return _fallback_summary(cleaned, max_words)


def _fallback_summary(text: str, max_words: int) -> str:
    words = text.split()
    short = " ".join(words[:max_words])
    if len(words) > max_words:
        short = short.rstrip(" ,.;:") + "."
    return short
