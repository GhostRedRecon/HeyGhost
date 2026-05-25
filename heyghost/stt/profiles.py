from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from heyghost.config import STTConfig
from heyghost.stt.whisper_cpp import WhisperCppSTT


DEFAULT_INSTALL_ROOT = os.environ.get("HEY_GHOST_INSTALL_ROOT", "/opt/hey-ghost")

DEFAULT_PROFILE_MODELS = {
    "fast": f"{DEFAULT_INSTALL_ROOT}/models/whisper/ggml-tiny.en.bin",
    "balanced": f"{DEFAULT_INSTALL_ROOT}/models/whisper/ggml-base.en.bin",
    "accurate": f"{DEFAULT_INSTALL_ROOT}/models/whisper/ggml-small.en.bin",
}


def profile_config(config: STTConfig, profile: str) -> STTConfig:
    profiles = config.profiles or {}
    overrides: dict[str, Any] = dict(profiles.get(profile, {}))
    if not overrides and profile in DEFAULT_PROFILE_MODELS:
        overrides["model_path"] = DEFAULT_PROFILE_MODELS[profile]
    if "model_path" in overrides and not Path(str(overrides["model_path"])).exists():
        overrides["model_path"] = config.model_path
    return replace(config, **overrides)


def build_whisper_stt(config: STTConfig, profile: str | None = None) -> WhisperCppSTT:
    selected = profile_config(config, profile or config.active_profile)
    return WhisperCppSTT(
        binary_path=selected.binary_path,
        model_path=selected.model_path,
        language=selected.language,
        threads=selected.threads,
        beam_size=selected.beam_size,
        best_of=selected.best_of,
        audio_context=selected.audio_context,
        temperature=selected.temperature,
        no_speech_threshold=selected.no_speech_threshold,
        split_on_word=selected.split_on_word,
        suppress_non_speech=selected.suppress_non_speech,
        no_fallback=selected.no_fallback,
        prompt=selected.prompt,
    )
