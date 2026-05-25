# Project Context

## Project

- Name: `Hey Ghost`
- Version: `0.1.0`
- Target OS: `Kali Linux`
- Target Hardware: `Intel N100`, `16 GB RAM`

## Product Direction

Hey Ghost is a local voice assistant intended to live as a lightweight Linux background service. The first version prioritizes:

- low latency
- low RAM usage
- simple native operation
- modular Python code
- explicit security boundaries

## v0.1.0 Boundaries

- No browser dashboard
- No Electron
- No cloud dependency for core STT, LLM, or TTS
- No automatic shell execution from model output
- No long-lived transcript memory
- No streaming generation in the initial release

## Default Stack

- Python 3
- Ollama with `qwen2.5:0.5b`
- `whisper.cpp`
- Piper
- WebRTC VAD
- `openwakeword` later, placeholder trigger now
- systemd
- YAML config

## State Machine

- `IDLE`
- `WAKE_DETECTED`
- `ACTIVE_LISTENING`
- `TRANSCRIBING`
- `THINKING`
- `SPEAKING`
- `FOLLOW_UP_LISTENING`

## Security Principles

- LLM output is treated as plain text, never a command
- Skills are explicit Python callables
- Risky actions require human confirmation
- Core loop is local-first and offline-capable except for the local Ollama HTTP call

## Practical Assumptions

- Audio I/O uses `sounddevice` in Python and `aplay` for WAV playback by default
- `whisper.cpp` and Piper binaries are managed outside the Python package
- Initial wake-word support is intentionally conservative so the rest of the loop can be validated first
