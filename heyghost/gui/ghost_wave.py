from __future__ import annotations

import math
import random
import time
import tkinter as tk

from heyghost.gui.command_console import CommandConsole
from heyghost.gui.diagnostics import DiagnosticsPanel
from heyghost.gui.theme import build_theme, dim_color


STATE_LABELS = {
    "idle": "Idle",
    "always_listening": "Always listening...",
    "wake_detected": "Hey Ghost heard",
    "listening": "Listening...",
    "transcribing": "Transcribing...",
    "thinking": "Thinking...",
    "speaking": "Speaking...",
    "follow_up_listening": "Listening for follow-up...",
    "uncertain": "I may have misheard",
    "error": "Local error",
}


class GhostWaveRenderer:
    def __init__(self, root, config) -> None:
        self.root = root
        self.config = config
        self.gui_config = getattr(config, "gui", config)
        self.wave_config = getattr(self.gui_config, "ghost_wave", None)
        self.theme = build_theme(self.gui_config)
        self.interval_ms = max(50, min(100, int(getattr(self.gui_config, "animation_interval_ms", 50))))
        requested_bars = int(getattr(self.wave_config, "waveform_bars", 64))
        self.bar_count = 32 if getattr(self.gui_config, "low_power_mode", True) else requested_bars
        self.bar_count = max(16, min(96, self.bar_count))
        self.state = "idle"
        self.status = STATE_LABELS["idle"]
        self.model_label = f"Ollama: {getattr(getattr(config, 'llm', None), 'model', 'local model')}"
        self.user_text = ""
        self.assistant_text = ""
        self.audio_level = 0.0
        self.metrics: dict = {}
        self.phase = 0.0
        self.last_audio_time = 0.0
        self.current_heights = [2.0 for _ in range(self.bar_count)]
        self.noise = [random.uniform(0.85, 1.18) for _ in range(self.bar_count)]
        self.tick_job: str | None = None

        self.canvas = tk.Canvas(
            root,
            bg=self.theme.background,
            bd=0,
            highlightthickness=0,
            cursor="none",
        )
        self.items: dict[str, int] = {}
        self.bars: list[int] = []
        self.glow_rings: list[int] = []
        self.diagnostics = DiagnosticsPanel(self.canvas, self.theme)
        self.command_console = CommandConsole(root, self.theme)

    def build(self) -> None:
        self.root.title("HeyGhost - GhostWave")
        self.root.configure(bg=self.theme.background)
        self.root.geometry("960x540")
        self.root.minsize(640, 360)
        if getattr(self.gui_config, "fullscreen", False):
            self.root.attributes("-fullscreen", True)
        self.canvas.pack(fill="both", expand=True)
        self.root.bind("<F12>", lambda _event: self.toggle_diagnostics())
        self.root.bind("<F10>", lambda _event: self.toggle_command_console())
        self.root.bind("<Control-grave>", lambda _event: self.toggle_command_console())

        self.items["title_ghost"] = self.canvas.create_text(
            0,
            0,
            text="Ghost",
            fill="#ffffff",
            font=("Impact", 24),
            anchor="center",
        )
        self.items["title_red"] = self.canvas.create_text(
            0,
            0,
            text="Red",
            fill="#ff2d2d",
            font=("Impact", 24),
            anchor="center",
        )
        self.items["title_recon"] = self.canvas.create_text(
            0,
            0,
            text="Recon",
            fill="#ffffff",
            font=("Impact", 24),
            anchor="center",
        )
        inactive = dim_color(self.theme.colors["idle"], 0.6)
        for _idx in range(self.bar_count):
            self.bars.append(
                self.canvas.create_line(0, 0, 0, 1, fill=inactive, width=3, capstyle="round")
            )
        for idx in range(3):
            ring = self.canvas.create_oval(0, 0, 1, 1, outline=dim_color(self.theme.colors["idle"], 0.28 - idx * 0.06), width=1)
            self.glow_rings.append(ring)
        self.items["center"] = self.canvas.create_oval(0, 0, 1, 1, fill=self.theme.colors["idle"], outline="")
        self.items["status"] = self.canvas.create_text(
            0,
            0,
            text=self.status,
            fill=self.theme.colors["text_primary"],
            font=(self.theme.font_family, self.theme.status_font_size),
            anchor="center",
        )
        self.items["user"] = self.canvas.create_text(
            0,
            0,
            text="You: -",
            fill=self.theme.colors["text_secondary"],
            font=(self.theme.font_family, self.theme.transcript_font_size),
            anchor="center",
            justify="center",
        )
        self.items["assistant"] = self.canvas.create_text(
            0,
            0,
            text="Ghost: -",
            fill=self.theme.colors["text_secondary"],
            font=(self.theme.font_family, self.theme.transcript_font_size),
            anchor="center",
            justify="center",
        )
        self.items["micro"] = self.canvas.create_text(
            0,
            0,
            text=self.model_label,
            fill=dim_color(self.theme.colors["text_secondary"], 0.72),
            font=(self.theme.font_family, 11),
            anchor="center",
        )
        self.diagnostics.build()
        self.diagnostics.update("model", getattr(getattr(self.config, "llm", None), "model", ""))
        self.diagnostics.set_visible(getattr(self.gui_config, "diagnostics_default", False))
        self.tick()

    def set_state(self, state: str) -> None:
        normalized = state if state in STATE_LABELS else "idle"
        self.state = normalized
        self.status = STATE_LABELS[normalized]
        self.diagnostics.update("state", normalized)

    def set_user_text(self, text: str) -> None:
        self.user_text = " ".join(str(text).split())[:240]
        self.diagnostics.update("raw transcript", self.user_text)

    def set_assistant_text(self, text: str) -> None:
        self.assistant_text = " ".join(str(text).split())[:260]

    def set_audio_level(self, level: float) -> None:
        self.audio_level = max(0.0, min(float(level), 1.0))
        self.last_audio_time = time.monotonic()

    def set_metrics(self, metrics: dict) -> None:
        self.metrics = dict(metrics)
        self.diagnostics.update_metrics(self.metrics)

    def handle_debug_event(self, event: dict) -> None:
        name = str(event.get("event", ""))
        text = str(event.get("text", "")).strip()
        if name == "audio_level":
            self.set_audio_level(float(event.get("level", 0.0) or 0.0))
            return
        if name == "always_listening":
            self.set_state("always_listening")
        elif name in {"idle_wake_word", "session_idle"}:
            self.set_state("idle")
        elif name in {"wake_detected", "session_started"}:
            self.set_state("wake_detected")
        elif name in {"speech_started", "listening"}:
            self.set_state("listening")
        elif name in {"speech_ended", "transcribing"}:
            self.set_state("transcribing")
        elif name == "stt_result":
            self.set_state("thinking")
            self.set_user_text(text or str(event.get("corrected_text", "")))
            self.diagnostics.update("corrected", str(event.get("corrected_text", "")))
            if "stt_ms" in event:
                self.diagnostics.update("stt", f"{event['stt_ms']} ms")
        elif name == "user_text" and text:
            self.set_user_text(text)
        elif name == "transcript_corrected":
            self.set_state("thinking")
            self.diagnostics.update("corrected", text)
        elif name == "route_selected":
            self.set_state("thinking")
            self.diagnostics.update("route", event.get("route", ""))
        elif name == "skill_result":
            if text:
                self.set_assistant_text(text)
                self.set_state("speaking")
        elif name == "llm_result":
            if text:
                self.set_assistant_text(text)
                self.set_state("speaking")
            llm_config = getattr(self.config, "llm", None)
            self.diagnostics.update("model", event.get("model", getattr(llm_config, "model", "")))
        elif name == "assistant_text" and text and text != self._acknowledgement():
            self.set_assistant_text(text)
        elif name in {"speaking", "tts_started"}:
            self.set_state("speaking")
        elif name == "tts_finished":
            self.set_state("follow_up_listening")
            if "tts_ms" in event:
                self.diagnostics.update("tts", f"{event['tts_ms']} ms")
        elif name == "turn_timing":
            self.set_metrics(event)
        elif name in {"low_confidence", "no_speech"}:
            self.set_state("uncertain")
        elif name == "error":
            self.set_state("error")
            self.status = text[:80] or STATE_LABELS["error"]
            self.diagnostics.update("last error", text)

    def toggle_diagnostics(self) -> None:
        self.diagnostics.toggle()

    def tick(self) -> None:
        self.phase += self._state_speed()
        if time.monotonic() - self.last_audio_time > 0.45:
            self.audio_level *= 0.86
            if self.audio_level < 0.02:
                self.audio_level = 0.0
        self.render()
        self.tick_job = self.root.after(self.interval_ms, self.tick)

    def render(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        center_x = width // 2
        center_y = int(height * 0.44)
        wave_width = int(width * float(getattr(self.wave_config, "waveform_width_ratio", 0.70)))
        wave_width = max(260, min(wave_width, width - 80))
        max_height = min(int(getattr(self.wave_config, "waveform_height", 150)), max(70, height // 3))
        color = self.theme.color_for_state(self.state)
        dim = dim_color(color, 0.42 if self.state == "idle" else 0.70)

        self.canvas.configure(bg=self.theme.background)
        self._render_brand(center_x, max(34, int(height * 0.10)))
        spacing = wave_width / max(1, self.bar_count - 1)
        start_x = center_x - wave_width / 2
        amplitude = self._state_amplitude()
        audio = self.audio_level if self.state in {"always_listening", "listening", "speaking"} else self.audio_level * 0.35
        smoothing = max(0.04, min(float(getattr(self.wave_config, "smoothing", 0.18)), 0.55))
        min_height = 2.0 if self.state == "idle" else 4.0

        for idx, item in enumerate(self.bars):
            distance = abs((idx / max(1, self.bar_count - 1)) - 0.5) * 2.0
            envelope = max(0.18, 1.0 - distance * 0.62)
            phase = self.phase + idx * 0.38
            secondary = math.sin(self.phase * 0.43 + idx * 0.21)
            procedural = abs(math.sin(phase) * 0.78 + secondary * 0.22) * amplitude * envelope
            if self.state == "uncertain":
                procedural *= 0.8 + ((idx % 5) * 0.05)
            target_amp = max(procedural, audio * envelope)
            target = min_height + (max_height / 2) * min(target_amp * self.noise[idx], 1.0)
            self.current_heights[idx] += (target - self.current_heights[idx]) * smoothing
            x = int(start_x + idx * spacing)
            bar_height = max(min_height, min(self.current_heights[idx], max_height / 2))
            if getattr(self.wave_config, "mirror_waveform", True):
                y0 = center_y - bar_height
                y1 = center_y + bar_height
            else:
                y0 = center_y
                y1 = center_y - bar_height
            self.canvas.coords(item, x, y0, x, y1)
            self.canvas.itemconfig(item, fill=color if idx % 3 else dim, width=2 if self.state == "idle" else 3)

        self._render_core(center_x, center_y, color)
        self.canvas.coords(self.items["status"], center_x, center_y + max_height // 2 + 46)
        self.canvas.itemconfig(self.items["status"], text=self.status, fill=self.theme.colors["text_primary"])
        text_width = max(280, min(int(width * 0.78), 820))
        self.canvas.coords(self.items["user"], center_x, int(height * 0.72))
        self.canvas.itemconfig(self.items["user"], text=f"You: {self._wrap(self.user_text or '-', 94)}", width=text_width)
        self.canvas.coords(self.items["assistant"], center_x, int(height * 0.80))
        self.canvas.itemconfig(self.items["assistant"], text=f"Ghost: {self._wrap(self.assistant_text or '-', 94)}", width=text_width)
        if getattr(self.wave_config, "show_micro_status", True):
            self.canvas.coords(self.items["micro"], center_x, center_y + max_height // 2 + 72)
            self.canvas.itemconfig(self.items["micro"], text=f"{self.state.replace('_', ' ')} | {self.model_label}")
        else:
            self.canvas.itemconfig(self.items["micro"], text="")
        self.diagnostics.render(width, height)
        self.command_console.render(width, height)

    def shutdown(self) -> None:
        if self.tick_job is not None:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        self.command_console.shutdown()

    def toggle_command_console(self) -> None:
        self.command_console.toggle()

    def _render_core(self, cx: int, cy: int, color: str) -> None:
        radius = int(getattr(self.wave_config, "center_dot_radius", 7))
        pulse = 1.0 + 0.22 * math.sin(self.phase * 0.8)
        if self.state == "wake_detected":
            pulse += 0.45 * abs(math.sin(self.phase * 1.8))
        if getattr(self.wave_config, "glow_enabled", True):
            for idx, item in enumerate(self.glow_rings):
                ring_r = radius * (2.4 + idx * 1.25) * pulse
                self.canvas.coords(item, cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r)
                self.canvas.itemconfig(item, outline=dim_color(color, max(0.10, 0.32 - idx * 0.08)))
        else:
            for item in self.glow_rings:
                self.canvas.itemconfig(item, outline=self.theme.background)
        if getattr(self.wave_config, "show_center_core", True):
            core_r = radius * pulse
            self.canvas.coords(self.items["center"], cx - core_r, cy - core_r, cx + core_r, cy + core_r)
            self.canvas.itemconfig(self.items["center"], fill=color)
        else:
            self.canvas.itemconfig(self.items["center"], fill=self.theme.background)

    def _render_brand(self, center_x: int, y: int) -> None:
        segments = (
            ("title_ghost", "Ghost"),
            ("title_red", "Red"),
            ("title_recon", "Recon"),
        )
        font = ("Impact", 24)
        # Tk Canvas does not expose text measurement without a font object; use bbox
        # on the already-created title items after setting the requested font.
        total_width = 0
        item_widths: list[int] = []
        for key, _text in segments:
            self.canvas.itemconfig(self.items[key], font=font)
            bbox = self.canvas.bbox(self.items[key])
            item_width = 52 if bbox is None else max(1, bbox[2] - bbox[0])
            item_widths.append(item_width)
            total_width += item_width
        x = center_x - total_width / 2
        for (key, _text), item_width in zip(segments, item_widths, strict=True):
            self.canvas.coords(self.items[key], x + item_width / 2, y)
            x += item_width

    def _state_amplitude(self) -> float:
        key = f"{self.state}_amplitude"
        if self.state in {"always_listening", "follow_up_listening"}:
            key = "listening_amplitude"
        return float(getattr(self.wave_config, key, getattr(self.wave_config, "idle_amplitude", 0.08)))

    def _state_speed(self) -> float:
        return {
            "idle": 0.10,
            "always_listening": 0.26,
            "wake_detected": 0.42,
            "listening": 0.32,
            "transcribing": 0.24,
            "thinking": 0.16,
            "speaking": 0.36,
            "follow_up_listening": 0.22,
            "uncertain": 0.28,
            "error": 0.08,
        }.get(self.state, 0.12)

    def _acknowledgement(self) -> str:
        assistant = getattr(self.config, "assistant", None)
        return str(getattr(assistant, "acknowledgement", ""))

    def _wrap(self, text: str, width: int) -> str:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) > width and current:
                lines.append(current)
                current = word
            else:
                current = candidate
            if len(lines) == 2:
                break
        if current and len(lines) < 2:
            lines.append(current)
        return "\n".join(lines)
