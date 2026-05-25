from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def analyze_debug_log(llm, debug_events_file: str, max_events: int = 40) -> str:
    events = _read_recent_events(debug_events_file, max_events)
    if not events:
        return "I do not have recent debug events to analyze."
    compact = "\n".join(json.dumps(event, sort_keys=True) for event in events)
    if llm is None:
        last = events[-1]
        return f"The latest debug event was {last.get('event', 'unknown')}. Check the recent route and transcript events for the likely cause."
    prompt = (
        "Analyze these HeyGhost debug events. Explain the likely cause of a wrong answer "
        "and suggest one practical fix. Use only these events. Do not invent system facts. "
        "Keep the response short for voice."
    )
    try:
        return llm.generate(prompt, compact[-6000:], "")
    except Exception:
        last = events[-1]
        return f"The latest debug event was {last.get('event', 'unknown')}. I could not summarize more detail."


def _read_recent_events(path: str, max_events: int) -> list[dict[str, Any]]:
    event_path = Path(path)
    try:
        lines = event_path.read_text(encoding="utf-8").splitlines()[-max_events:]
    except OSError:
        return []
    events = []
    for line in lines:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events
