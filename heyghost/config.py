from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


DEFAULT_INSTALL_ROOT = os.environ.get("HEY_GHOST_INSTALL_ROOT", "/opt/hey-ghost")
DEFAULT_CONFIG_ROOT = os.environ.get("HEY_GHOST_CONFIG_ROOT", "/etc/hey-ghost")
DEFAULT_LOG_DIR = os.environ.get("HEY_GHOST_LOG_DIR", "/var/log/hey-ghost")


@dataclass
class AssistantConfig:
    name: str
    wake_phrase: str
    mode: str
    follow_up_timeout_seconds: int
    max_response_words: int
    acknowledgement: str
    session_timeout_seconds: int = 30


@dataclass
class LLMConfig:
    provider: str
    model: str
    url: str
    num_ctx: int
    num_predict: int
    temperature: float
    keep_alive: str = "10m"


@dataclass
class STTConfig:
    engine: str
    model_path: str
    binary_path: str
    language: str
    threads: int = 4
    beam_size: int = 8
    best_of: int = 8
    audio_context: int = 0
    temperature: float = 0.0
    no_speech_threshold: float = 0.45
    split_on_word: bool = True
    suppress_non_speech: bool = True
    no_fallback: bool = True
    prompt: str = ""
    ignored_phrases: tuple[str, ...] = ()
    min_confidence: float = 0.65
    active_profile: str = "fast"
    retry_profile: str = "balanced"
    retry_on_low_confidence: bool = True
    profiles: dict[str, dict[str, Any]] | None = None


@dataclass
class TTSConfig:
    engine: str
    binary_path: str
    model_path: str
    speaker_wav_path: str
    length_scale: float = 0.9
    sentence_silence: float = 0.05


@dataclass
class AudioConfig:
    sample_rate: int
    channels: int
    input_device: Optional[int]
    output_device: Optional[int]
    silence_timeout_ms: int
    min_speech_ms: int
    frame_duration_ms: int
    max_record_seconds: int
    preroll_ms: int = 300
    vad_backend: str = "webrtc"
    vad_aggressiveness: int = 3


@dataclass
class WakeWordConfig:
    engine: str
    sensitivity: float
    dev_trigger_file: str
    poll_interval_ms: int
    model_name: str = "hey_jarvis"
    session_mode: str = "wake_word_session"


@dataclass
class ConversationConfig:
    keep_last_turns: int
    memory_path: str = f"{DEFAULT_INSTALL_ROOT}/shared/conversation-memory.sqlite3"
    summary_max_chars: int = 1200
    max_persistent_messages: int = 200


@dataclass
class LoggingConfig:
    level: str
    log_file: str = f"{DEFAULT_LOG_DIR}/hey-ghost.log"
    debug_events_file: str = f"{DEFAULT_INSTALL_ROOT}/shared/debug-events.jsonl"


@dataclass
class RoutingConfig:
    structured_output: bool = False
    min_route_confidence: float = 0.55
    enable_rag_placeholder: bool = True
    low_confidence_clarify: bool = True


@dataclass
class LLMCapabilitiesConfig:
    enabled: bool = True
    model_fast: str = "qwen2.5:0.5b"
    model_quality: str = "gemma3:1b"
    use_structured_outputs: bool = True
    use_tool_calling: bool = False
    max_spoken_words: int = 55
    explain_command_results: bool = True
    summarize_notes: bool = True
    analyze_logs: bool = True
    local_rag_enabled: bool = True
    vision_enabled: bool = False


@dataclass
class RAGConfig:
    enabled: bool = True
    embedding_model: str = "nomic-embed-text"
    knowledge_dir: str = f"{DEFAULT_INSTALL_ROOT}/knowledge"
    index_path: str = f"{DEFAULT_INSTALL_ROOT}/shared/rag-index.sqlite3"
    chunk_chars: int = 800
    chunk_overlap: int = 120
    top_k: int = 4
    require_sources: bool = True


@dataclass
class GhostWaveConfig:
    waveform_bars: int = 64
    waveform_width_ratio: float = 0.70
    waveform_height: int = 150
    center_dot_radius: int = 7
    idle_amplitude: float = 0.08
    listening_amplitude: float = 0.85
    thinking_amplitude: float = 0.28
    speaking_amplitude: float = 0.65
    smoothing: float = 0.18
    glow_enabled: bool = True
    mirror_waveform: bool = True
    show_center_core: bool = True
    show_micro_status: bool = True


@dataclass
class GUIColorsConfig:
    idle: str = "#64748b"
    wake_detected: str = "#22c55e"
    listening: str = "#00ffaa"
    transcribing: str = "#38bdf8"
    thinking: str = "#60a5fa"
    speaking: str = "#22d3ee"
    uncertain: str = "#facc15"
    error: str = "#f87171"
    text_primary: str = "#e5e7eb"
    text_secondary: str = "#94a3b8"
    panel: str = "#0f172a"


@dataclass
class GUIConfig:
    enabled: bool = True
    style: str = "ghost_wave"
    fullscreen: bool = False
    low_power_mode: bool = True
    animation_interval_ms: int = 50
    background: str = "#030712"
    font_family: str = "Inter"
    fallback_font_family: str = "DejaVu Sans"
    title_font_size: int = 18
    status_font_size: int = 14
    transcript_font_size: int = 12
    diagnostics_default: bool = False
    ghost_wave: GhostWaveConfig = field(default_factory=GhostWaveConfig)
    colors: GUIColorsConfig = field(default_factory=GUIColorsConfig)


@dataclass
class SafetyConfig:
    require_confirmation_for_risky_actions: bool = True
    defensive_cyber_only: bool = True
    health_is_general_wellness: bool = True
    prevent_system_status_hallucination: bool = True


@dataclass
class ObservabilityConfig:
    enabled: bool = True
    include_turn_id: bool = True
    log_timing: bool = True


@dataclass
class AppConfig:
    assistant: AssistantConfig
    llm: LLMConfig
    stt: STTConfig
    tts: TTSConfig
    audio: AudioConfig
    wake_word: WakeWordConfig
    conversation: ConversationConfig
    logging: LoggingConfig
    routing: RoutingConfig
    llm_capabilities: LLMCapabilitiesConfig
    rag: RAGConfig
    gui: GUIConfig
    safety: SafetyConfig
    observability: ObservabilityConfig
    source_path: str


DEFAULT_CONFIG_LOCATIONS = (
    "config.yaml",
    f"{DEFAULT_CONFIG_ROOT}/config.yaml",
)


ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_string(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        if name in os.environ:
            return os.environ[name]
        if default is not None:
            return default
        return match.group(0)

    return os.path.expanduser(ENV_VAR_RE.sub(replace, os.path.expandvars(value)))


def _expand_config_values(value: Any) -> Any:
    if isinstance(value, str):
        return _expand_string(value)
    if isinstance(value, list):
        return [_expand_config_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_config_values(item) for key, item in value.items()}
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a YAML mapping")
    return _expand_config_values(data)


def resolve_config_path(explicit_path: str | None = None) -> Path:
    candidates = []

    if explicit_path:
        candidates.append(Path(explicit_path))

    env_path = os.environ.get("HEY_GHOST_CONFIG")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(Path(item) for item in DEFAULT_CONFIG_LOCATIONS)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "No config file found. Checked explicit path, HEY_GHOST_CONFIG, "
        f"./config.yaml, and {DEFAULT_CONFIG_ROOT}/config.yaml."
    )


def load_config(explicit_path: str | None = None) -> AppConfig:
    path = resolve_config_path(explicit_path)
    raw = _load_yaml(path)
    stt_raw = dict(raw["stt"])
    if "ignored_phrases" in stt_raw:
        stt_raw["ignored_phrases"] = tuple(stt_raw["ignored_phrases"] or ())

    assistant_raw = dict(raw["assistant"])
    if "session_timeout_seconds" not in assistant_raw:
        assistant_raw["session_timeout_seconds"] = assistant_raw.get("follow_up_timeout_seconds", 30)

    audio_raw = dict(raw["audio"])
    audio_raw.setdefault("vad_backend", "webrtc")
    audio_raw.setdefault("vad_aggressiveness", 3)

    wake_raw = dict(raw["wake_word"])
    wake_raw.setdefault("session_mode", raw.get("assistant", {}).get("mode", "wake_word_session"))

    gui_raw = dict(raw.get("gui", {}))
    gui_raw["ghost_wave"] = GhostWaveConfig(**dict(gui_raw.get("ghost_wave", {})))
    gui_raw["colors"] = GUIColorsConfig(**dict(gui_raw.get("colors", {})))

    return AppConfig(
        assistant=AssistantConfig(**assistant_raw),
        llm=LLMConfig(**raw["llm"]),
        stt=STTConfig(**stt_raw),
        tts=TTSConfig(**raw["tts"]),
        audio=AudioConfig(**audio_raw),
        wake_word=WakeWordConfig(**wake_raw),
        conversation=ConversationConfig(**raw["conversation"]),
        logging=LoggingConfig(**raw["logging"]),
        routing=RoutingConfig(**raw.get("routing", {})),
        llm_capabilities=LLMCapabilitiesConfig(**raw.get("llm_capabilities", {})),
        rag=RAGConfig(**raw.get("rag", {})),
        gui=GUIConfig(**gui_raw),
        safety=SafetyConfig(**raw.get("safety", {})),
        observability=ObservabilityConfig(**raw.get("observability", {})),
        source_path=str(path),
    )
