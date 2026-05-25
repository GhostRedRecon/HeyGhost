from __future__ import annotations

import json
from pathlib import Path

from heyghost.routing import TurnRouter
from heyghost.skills.registry import SkillRegistry
from heyghost.stt.filter import TranscriptFilter


def replay_transcripts(path: str) -> int:
    fixture = Path(path)
    if not fixture.exists():
        raise FileNotFoundError(path)

    transcript_filter = TranscriptFilter()
    router = TurnRouter(SkillRegistry())
    total = 0
    handled = 0
    for line in fixture.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        payload = json.loads(line)
        raw = str(payload.get("text", ""))
        expected = payload.get("expect_source")
        correction = transcript_filter.clean_with_result(raw)
        route = router.route(correction.cleaned_text)
        if route.handled:
            handled += 1
        status = "ok"
        if expected and route.route != expected:
            status = "mismatch"
        print(
            json.dumps(
                {
                    "status": status,
                    "raw": raw,
                    "cleaned": correction.cleaned_text,
                    "route": route.route,
                    "expected": expected,
                    "handled": route.handled,
                },
                ensure_ascii=True,
            )
        )
    print(f"replay summary: {handled}/{total} handled")
    return 0
