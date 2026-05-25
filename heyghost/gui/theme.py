from __future__ import annotations

import tkinter.font as tkfont
from dataclasses import dataclass


@dataclass(frozen=True)
class GhostWaveTheme:
    background: str
    font_family: str
    title_font_size: int
    status_font_size: int
    transcript_font_size: int
    colors: dict[str, str]

    def color_for_state(self, state: str) -> str:
        if state == "follow_up_listening":
            return self.colors.get("listening", "#00ffaa")
        return self.colors.get(state, self.colors.get("idle", "#64748b"))


def build_theme(gui_config) -> GhostWaveTheme:
    requested = getattr(gui_config, "font_family", "Inter")
    fallback = getattr(gui_config, "fallback_font_family", "DejaVu Sans")
    family = requested if requested in set(tkfont.families()) else fallback
    colors_obj = getattr(gui_config, "colors", None)
    colors = {
        "idle": getattr(colors_obj, "idle", "#64748b"),
        "wake_detected": getattr(colors_obj, "wake_detected", "#22c55e"),
        "listening": getattr(colors_obj, "listening", "#00ffaa"),
        "transcribing": getattr(colors_obj, "transcribing", "#38bdf8"),
        "thinking": getattr(colors_obj, "thinking", "#60a5fa"),
        "speaking": getattr(colors_obj, "speaking", "#22d3ee"),
        "uncertain": getattr(colors_obj, "uncertain", "#facc15"),
        "error": getattr(colors_obj, "error", "#f87171"),
        "text_primary": getattr(colors_obj, "text_primary", "#e5e7eb"),
        "text_secondary": getattr(colors_obj, "text_secondary", "#94a3b8"),
        "panel": getattr(colors_obj, "panel", "#0f172a"),
    }
    return GhostWaveTheme(
        background=getattr(gui_config, "background", "#030712"),
        font_family=family,
        title_font_size=getattr(gui_config, "title_font_size", 18),
        status_font_size=getattr(gui_config, "status_font_size", 14),
        transcript_font_size=getattr(gui_config, "transcript_font_size", 12),
        colors=colors,
    )


def dim_color(color: str, factor: float) -> str:
    factor = max(0.0, min(1.0, factor))
    try:
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
    except (ValueError, IndexError):
        return color
    return f"#{int(red * factor):02x}{int(green * factor):02x}{int(blue * factor):02x}"
