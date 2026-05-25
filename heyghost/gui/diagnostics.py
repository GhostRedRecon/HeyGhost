from __future__ import annotations

import textwrap


class DiagnosticsPanel:
    def __init__(self, canvas, theme) -> None:
        self.canvas = canvas
        self.theme = theme
        self.visible = False
        self.values: dict[str, str] = {
            "state": "idle",
            "raw transcript": "",
            "corrected": "",
            "route": "",
            "model": "",
            "stt": "",
            "llm": "",
            "tts": "",
            "total": "",
            "last error": "",
        }
        self.panel = None
        self.text_items: list[int] = []

    def build(self) -> None:
        self.panel = self.canvas.create_rectangle(0, 0, 1, 1, fill=self.theme.colors["panel"], outline="#1f2937", width=1, state="hidden")
        for _idx in range(len(self.values)):
            item = self.canvas.create_text(
                0,
                0,
                text="",
                fill=self.theme.colors["text_secondary"],
                anchor="nw",
                font=(self.theme.font_family, 9),
                state="hidden",
            )
            self.text_items.append(item)

    def set_visible(self, visible: bool) -> None:
        self.visible = visible
        state = "normal" if visible else "hidden"
        if self.panel is not None:
            self.canvas.itemconfig(self.panel, state=state)
        for item in self.text_items:
            self.canvas.itemconfig(item, state=state)

    def toggle(self) -> None:
        self.set_visible(not self.visible)

    def update(self, key: str, value: object) -> None:
        if key in self.values:
            self.values[key] = str(value)[:140]

    def update_metrics(self, metrics: dict) -> None:
        mapping = {
            "stt": "stt_ms",
            "llm": "llm_ms",
            "tts": "tts_ms",
            "total": "total_ms",
        }
        for label, key in mapping.items():
            if key in metrics:
                self.values[label] = f"{metrics[key]} ms"
        if "response_ms" in metrics and not self.values.get("llm"):
            self.values["llm"] = f"{metrics['response_ms']} ms"

    def render(self, width: int, height: int) -> None:
        if self.panel is None:
            return
        panel_w = min(430, max(300, int(width * 0.42)))
        panel_h = 230
        x0 = width - panel_w - 20
        y0 = height - panel_h - 20
        x1 = width - 20
        y1 = height - 20
        self.canvas.coords(self.panel, x0, y0, x1, y1)
        lines = list(self.values.items())
        y = y0 + 14
        for item, (label, value) in zip(self.text_items, lines, strict=True):
            wrapped = textwrap.shorten(value, width=46, placeholder="...")
            self.canvas.coords(item, x0 + 14, y)
            self.canvas.itemconfig(item, text=f"{label}: {wrapped}")
            y += 22
