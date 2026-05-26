from __future__ import annotations

import time
from types import SimpleNamespace

from heyghost.app import GhostApp


def _app() -> GhostApp:
    app = object.__new__(GhostApp)
    app.config = SimpleNamespace(
        assistant=SimpleNamespace(
            wake_phrase="hey ghost",
            follow_up_timeout_seconds=12,
        )
    )
    app._active_conversation_until = 0.0
    return app


def test_attention_allows_wake_addressed_transcript() -> None:
    app = _app()

    assert app._has_attention(
        "what time is it",
        raw_text="Hey Ghost what time is it",
        correction_reason="wake_phrase_removed",
        continuous=True,
    )


def test_attention_allows_active_followup_without_wake_phrase() -> None:
    app = _app()
    app._active_conversation_until = time.monotonic() + 10

    assert app._has_attention("make that shorter", continuous=True)


def test_attention_allows_clear_direct_assistant_request() -> None:
    app = _app()

    assert app._has_attention("how much memory do i have", continuous=True)


def test_attention_rejects_background_statement() -> None:
    app = _app()

    assert not app._has_attention("a terminal is a text interface to the shell", continuous=True)


def test_attention_is_bypassed_for_manual_sessions() -> None:
    app = _app()

    assert app._has_attention("a terminal is a text interface to the shell", continuous=False)
