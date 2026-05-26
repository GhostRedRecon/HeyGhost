from __future__ import annotations

import time

from heyghost.app import GhostApp


def _app_with_last_spoken(text: str, seconds: float = 2.0) -> GhostApp:
    app = object.__new__(GhostApp)
    app._last_spoken_text = text
    app._ignore_self_audio_until = time.monotonic() + seconds
    return app


def test_self_echo_matches_recent_assistant_response() -> None:
    app = _app_with_last_spoken("It is 10:45 on Tuesday.")

    assert app._looks_like_self_echo("what time is it it is 10:45 on Tuesday")


def test_self_echo_expires_after_cooldown() -> None:
    app = _app_with_last_spoken("It is 10:45 on Tuesday.", seconds=-1.0)

    assert not app._looks_like_self_echo("it is 10:45 on Tuesday")


def test_self_echo_does_not_block_unrelated_followup() -> None:
    app = _app_with_last_spoken("It is 10:45 on Tuesday.")

    assert not app._looks_like_self_echo("open the terminal")
