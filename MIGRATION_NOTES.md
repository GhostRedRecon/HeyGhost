# HeyGhost Migration Notes

## From `always_on` to `wake_word_session`

Previous debug behavior used:

```yaml
wake_word:
  engine: "always_on"
```

That mode records repeatedly and can react to background speech. It remains useful
for debugging microphone, STT, and TTS behavior, but it is not the production
interaction model.

The production default is now:

```yaml
assistant:
  mode: "wake_word_session"
  session_timeout_seconds: 30

wake_word:
  engine: "openwakeword"
  session_mode: "wake_word_session"
```

Behavior:

1. `IDLE_WAKE_WORD`: wait for wake phrase or manual trigger.
2. `ACTIVE_SESSION`: after wake, listen for follow-up speech without requiring the
   wake phrase again.
3. The active session ends after roughly 25-30 seconds of idle follow-up time.

If `openwakeword` is not installed or no model is available, HeyGhost still
supports the manual trigger file at `/opt/hey-ghost/shared/heyghost_wake`.

To temporarily restore debug behavior:

```yaml
wake_word:
  engine: "always_on"
```

Do not use `always_on` as the normal production mode unless the operator accepts
background speech activation.

## STT Profiles

HeyGhost now supports:

- `fast`: whisper tiny.en
- `balanced`: whisper base.en
- `accurate`: whisper small.en

The runtime starts with `fast` and can retry suspicious or low-confidence
transcripts with `balanced`. If the larger model file is missing, the retry
profile falls back to the configured fast model instead of failing.

## Observability

Debug events now include turn IDs and richer pipeline events:

- `wake_detected`
- `speech_started`
- `speech_ended`
- `stt_result`
- `transcript_corrected`
- `route_selected`
- `skill_result`
- `llm_result`
- `tts_started`
- `tts_finished`
- `turn_timing`

Use `/opt/hey-ghost/shared/debug-events.jsonl` to diagnose strange answers.
