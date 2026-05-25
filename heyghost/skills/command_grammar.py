from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class GrammarMatch:
    text: str
    intent: str
    confidence: float
    reason: str


EXACT_ALIASES: dict[str, tuple[str, str]] = {
    "what can you do": ("what are your capabilities", "capabilities"),
    "what are your capabilities": ("what are your capabilities", "capabilities"),
    "what are your cap abilities": ("what are your capabilities", "capabilities"),
    "what are your capability": ("what are your capabilities", "capabilities"),
    "what are your capablties": ("what are your capabilities", "capabilities"),
    "what are your capblities": ("what are your capabilities", "capabilities"),
    "show your capabilities": ("show your llm capabilities", "capabilities"),
    "show your capability": ("show your llm capabilities", "capabilities"),
    "show your cap abilities": ("show your llm capabilities", "capabilities"),
    "show your llm capabilities": ("show your llm capabilities", "capabilities"),
    "what are you doing with me": ("what are your capabilities", "capabilities"),
    "what are you giving me": ("what are your capabilities", "capabilities"),
    "what are you kiwi b": ("what are your capabilities", "capabilities"),
    "what are you qb": ("what are your capabilities", "capabilities"),
    "what time is it": ("what time is it", "time"),
    "tell me the time": ("what time is it", "time"),
    "current time": ("what time is it", "time"),
    "how much ram do you have": ("how much ram does the system have", "memory"),
    "how much memory do you have": ("how much ram does the system have", "memory"),
    "memory status": ("memory status", "memory"),
    "cpu info": ("cpu info", "cpu"),
    "processor info": ("cpu info", "cpu"),
    "which model are you running": ("which model are you running", "model"),
    "what model are you using": ("which model are you running", "model"),
    "what os are you running": ("what os are you running", "os"),
    "what operating system are you running": ("what operating system are you running", "os"),
    "system status": ("system status", "system_status"),
    "disk space": ("disk space", "storage"),
    "storage status": ("storage status", "storage"),
    "explain that result": ("explain that result", "explain_result"),
    "explain the result": ("explain that result", "explain_result"),
    "make that shorter": ("make that shorter", "shorten"),
    "why did you answer wrong": ("why did you answer wrong", "log_analysis"),
    "why did you get that wrong": ("why did you answer wrong", "log_analysis"),
    "teach me about linux networking": ("teach me about linux networking", "teaching"),
    "suggest a config change": ("suggest a config change", "config_suggestion"),
    "what is connected to usb": ("what is connected to the usb", "usb_devices"),
    "what is connected to the usb": ("what is connected to the usb", "usb_devices"),
    "what is coming through today usb": ("what is connected to the usb", "usb_devices"),
    "what is coming through the usb": ("what is connected to the usb", "usb_devices"),
    "what is connected today usb": ("what is connected to the usb", "usb_devices"),
    "what is connecting to usb": ("what is connected to the usb", "usb_devices"),
    "what is connecting to the usb": ("what is connected to the usb", "usb_devices"),
    "what is connected usb": ("what is connected to the usb", "usb_devices"),
    "what usb devices are connected": ("what is connected to the usb", "usb_devices"),
    "list usb devices": ("what is connected to the usb", "usb_devices"),
    "show usb devices": ("what is connected to the usb", "usb_devices"),
    "what tools are there in linux": ("what tools are there in linux", "linux_tools"),
    "what linux tools are there": ("what tools are there in linux", "linux_tools"),
    "what tools are installed": ("what tools are there in linux", "linux_tools"),
    "list linux tools": ("what tools are there in linux", "linux_tools"),
    "show linux tools": ("what tools are there in linux", "linux_tools"),
}


PREFIX_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("summarize this note", "summarize this note", "note_summary"),
    ("summarize note", "summarize this note", "note_summary"),
    ("classify this request", "classify this request", "classifier"),
    ("classify request", "classify this request", "classifier"),
    ("search your local knowledge for", "search your local knowledge for", "rag"),
    ("search local knowledge for", "search your local knowledge for", "rag"),
    ("turn this into action items", "turn this into action items", "action_items"),
    ("action items", "turn this into action items", "action_items"),
    ("open website", "open website", "action"),
    ("open the website", "open website", "action"),
    ("open browser", "open browser", "action"),
    ("open the browser", "open browser", "action"),
)


FUZZY_PHRASES: tuple[tuple[str, str, str], ...] = tuple(
    (alias, canonical, intent) for alias, (canonical, intent) in EXACT_ALIASES.items()
) + tuple((alias, canonical, intent) for alias, canonical, intent in PREFIX_ALIASES)


COMMAND_HINTS = {
    "what",
    "show",
    "tell",
    "how",
    "which",
    "open",
    "search",
    "summarize",
    "classify",
    "make",
    "turn",
    "suggest",
    "teach",
    "explain",
    "why",
    "system",
    "disk",
    "cpu",
    "memory",
    "usb",
    "tools",
    "tool",
}


def canonicalize_command(normalized: str) -> GrammarMatch | None:
    text = " ".join(normalized.split())
    if not text:
        return None

    exact = EXACT_ALIASES.get(text)
    if exact is not None:
        canonical, intent = exact
        return GrammarMatch(canonical, intent, 1.0, "exact_alias")

    for alias, canonical_prefix, intent in PREFIX_ALIASES:
        if text == alias:
            return GrammarMatch(canonical_prefix, intent, 1.0, "prefix_alias")
        if text.startswith(f"{alias} "):
            suffix = text[len(alias) :].strip()
            return GrammarMatch(f"{canonical_prefix} {suffix}".strip(), intent, 1.0, "prefix_alias")

    if not _looks_like_command(text):
        return None

    best = _best_fuzzy(text)
    if best is None:
        return None
    alias, canonical, intent, score = best
    threshold = 0.72 if intent == "capabilities" else 0.82
    if score < threshold:
        return None
    if alias in {item[0] for item in PREFIX_ALIASES} and len(text) > len(alias):
        return None
    return GrammarMatch(canonical, intent, score, "fuzzy_alias")


def _looks_like_command(text: str) -> bool:
    words = text.split()
    if not words or len(words) > 12:
        return False
    return words[0] in COMMAND_HINTS or any(word in COMMAND_HINTS for word in words[:3])


def _best_fuzzy(text: str) -> tuple[str, str, str, float] | None:
    best: tuple[str, str, str, float] | None = None
    for alias, canonical, intent in FUZZY_PHRASES:
        score = SequenceMatcher(None, text, alias).ratio()
        if best is None or score > best[3]:
            best = (alias, canonical, intent, score)
    return best
