from __future__ import annotations


def generate_followups(llm, user_text: str, answer_text: str) -> list[str]:
    if llm is None:
        return []
    prompt = (
        "Suggest up to two short follow-up questions for a voice assistant. "
        "Return one question per line. Do not include commands or file changes."
    )
    try:
        raw = llm.generate(prompt, f"User: {user_text}\nAnswer: {answer_text}", "")
    except Exception:
        return []
    questions = []
    for line in raw.splitlines():
        cleaned = line.strip(" -0123456789.").strip()
        if cleaned.endswith("?"):
            questions.append(cleaned)
        if len(questions) == 2:
            break
    return questions
