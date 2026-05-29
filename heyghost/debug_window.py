from __future__ import annotations

import json
import math
import os
import shutil
import sys
import subprocess
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from heyghost.config import AppConfig
from heyghost.gui import GhostWaveRenderer

SERVICE_NAME = "hey-ghost.service"
VISUAL_MODE = True


def run_debug_window(config: AppConfig, on_close=None, standalone: bool = False) -> int:
    if getattr(config.gui, "style", "ghost_wave") == "ghost_wave":
        app = GhostWaveWindow(config, on_close=on_close, standalone=standalone)
        app.run()
        return 0
    app = FuturisticWindow(config)
    app.run()
    return 0


class GhostWaveWindow:
    def __init__(self, config: AppConfig, on_close=None, standalone: bool = False) -> None:
        self.config = config
        self.on_close = on_close
        self.standalone = standalone
        self.events_path = Path(config.logging.debug_events_file)
        self.offset = 0
        self.root = tk.Tk()
        self.renderer = GhostWaveRenderer(self.root, config)
        self.renderer.build()
        self.poll_job: str | None = None
        self.status_job: str | None = None
        self.trigger_busy = False
        self.fullscreen = bool(getattr(config.gui, "fullscreen", False))
        self.handled_actions: set[str] = set()
        self.last_terminal_window: str | None = None

        self.root.bind("<Escape>", lambda _event: self._on_close())
        self.root.bind("<space>", lambda _event: self._trigger())
        self.root.bind("<Return>", lambda _event: self._trigger())
        self.root.bind("<F11>", lambda _event: self._toggle_fullscreen())
        self.renderer.canvas.bind("<Button-1>", lambda _event: self._trigger())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._load_recent_events()
        self._refresh_service_status()
        self._poll_events()

    def run(self) -> None:
        self.root.mainloop()

    def _on_close(self) -> None:
        if self.on_close is not None:
            self.on_close()
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
        if self.status_job is not None:
            self.root.after_cancel(self.status_job)
        self.renderer.shutdown()
        self.root.destroy()

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def _load_recent_events(self) -> None:
        if self.standalone:
            self.offset = 0
            return
        if self.events_path.exists():
            self.offset = self.events_path.stat().st_size

    def _poll_events(self) -> None:
        if self.events_path.exists():
            size = self.events_path.stat().st_size
            if size < self.offset:
                self.offset = 0
            if size > self.offset:
                with self.events_path.open("r", encoding="utf-8") as handle:
                    handle.seek(self.offset)
                    for line in handle:
                        self._render_event_line(line)
                    self.offset = handle.tell()
        self.poll_job = self.root.after(180, self._poll_events)

    def _render_event_line(self, raw_line: str) -> None:
        try:
            payload = json.loads(raw_line.strip())
        except json.JSONDecodeError:
            return
        self.renderer.handle_debug_event(payload)
        if payload.get("event") == "action_request":
            self._handle_action_request(payload)

    def _refresh_service_status(self) -> None:
        if self.standalone:
            self.renderer.diagnostics.update("model", self.config.llm.model)
            self.renderer.diagnostics.update("last error", "")
            self._refresh_audio_volumes()
            self.status_job = self.root.after(2500, self._refresh_service_status)
            return
        try:
            result = subprocess.run(
                ["systemctl", "is-active", SERVICE_NAME],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            status = result.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            status = "unknown"
        self.renderer.diagnostics.update("model", self.config.llm.model)
        self.renderer.diagnostics.update("last error", "" if status == "active" else f"service {status}")
        self._refresh_audio_volumes()
        self.status_job = self.root.after(2500, self._refresh_service_status)

    def _refresh_audio_volumes(self) -> None:
        volumes = self._read_audio_volumes()
        self.renderer.set_output_volume(
            level=volumes.get("speaker"),
            mic_level=volumes.get("mic"),
        )

    def _read_audio_volumes(self) -> dict[str, float]:
        volumes: dict[str, float] = {}
        if shutil.which("wpctl"):
            mapping = {
                "speaker": "@DEFAULT_AUDIO_SINK@",
                "mic": "@DEFAULT_AUDIO_SOURCE@",
            }
            for key, target in mapping.items():
                try:
                    result = subprocess.run(
                        ["wpctl", "get-volume", target],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )
                except (OSError, subprocess.SubprocessError):
                    continue
                if result.returncode == 0:
                    value = self._parse_wpctl_volume(result.stdout)
                    if value is not None:
                        volumes[key] = value
        return volumes

    def _parse_wpctl_volume(self, text: str) -> float | None:
        for part in text.replace(":", " ").split():
            try:
                value = float(part)
            except ValueError:
                continue
            return max(0.0, min(value, 1.0))
        return None

    def _trigger(self) -> None:
        if self.trigger_busy:
            return
        self.trigger_busy = True
        threading.Thread(target=self._run_trigger, daemon=True).start()

    def _run_trigger(self) -> None:
        if self.standalone:
            try:
                wake_path = Path(self.config.wake_word.dev_trigger_file)
                session_path = wake_path.with_name("heyghost_session")
                wake_path.parent.mkdir(parents=True, exist_ok=True)
                session_path.unlink(missing_ok=True)
                wake_path.write_text("wake\n", encoding="utf-8")
                self.root.after(0, lambda: self.renderer.handle_debug_event({"event": "session_started", "text": "Listening"}))
            except OSError as exc:
                self.root.after(0, lambda: self.renderer.handle_debug_event({"event": "error", "text": str(exc)}))
            self.root.after(0, self._finish_trigger)
            return

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "heyghost.py"),
                    "--config",
                    self.config.source_path,
                    "trigger",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.root.after(0, lambda: self.renderer.handle_debug_event({"event": "error", "text": str(exc)}))
            self.root.after(0, self._finish_trigger)
            return
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Trigger failed"
            self.root.after(0, lambda: self.renderer.handle_debug_event({"event": "error", "text": message}))
        self.root.after(0, self._finish_trigger)

    def _finish_trigger(self) -> None:
        self.trigger_busy = False

    def _handle_action_request(self, payload: dict[str, object]) -> None:
        action = payload.get("action")
        if not isinstance(action, dict):
            return
        action_id = self._action_id(payload, action)
        if action_id in self.handled_actions:
            return
        self.handled_actions.add(action_id)
        threading.Thread(target=self._run_desktop_action, args=(action,), daemon=True).start()

    def _action_id(self, payload: dict[str, object], action: dict[str, object]) -> str:
        stamp = str(payload.get("ts", ""))
        kind = str(action.get("kind", ""))
        url = str(action.get("url", ""))
        command = action.get("command")
        command_text = " ".join(command) if isinstance(command, list) else ""
        target = str(action.get("target", ""))
        return f"{stamp}:{kind}:{url}:{target}:{command_text}"

    def _run_desktop_action(self, action: dict[str, object]) -> None:
        kind = str(action.get("kind", ""))
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        if kind in {"browser", "website", "search"}:
            target = str(action.get("url", "about:blank")).strip() or "about:blank"
            subprocess.run(["xdg-open", target], check=False, capture_output=True, text=True, timeout=10, env=env)
            return
        if kind == "linux_app":
            command = action.get("command")
            if isinstance(command, list) and command:
                subprocess.Popen([str(part) for part in command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            return
        if kind == "close_app":
            self._close_app(str(action.get("target", "")), env)
            return
        if kind == "terminal":
            prompt = str(action.get("prompt", "HeyGhost terminal ready. Say a command for me to run."))
            self._launch_terminal(["bash"], env, prompt=prompt)
            return
        if kind == "ssh":
            command = action.get("command")
            if isinstance(command, list):
                self._launch_terminal(command, env)
            return
        if kind == "terminal_input":
            text = str(action.get("text", ""))
            enter = bool(action.get("enter", True))
            if not self._send_terminal_text(text, enter, env) and text:
                self._launch_terminal(["bash"], env, prompt=f"$ {text}", initial_command=text)
            return
        if kind == "terminal_key":
            self._send_terminal_key(str(action.get("key", "")), env)

    def _launch_terminal(
        self,
        command: list[str],
        env: dict[str, str],
        prompt: str = "",
        initial_command: str = "",
    ) -> None:
        terminal = self._find_terminal()
        if terminal is None:
            self.root.after(0, lambda: self.renderer.handle_debug_event({"event": "error", "text": "No terminal emulator was found."}))
            return
        command_text = " ".join(command)
        safe_prompt = prompt.replace("\\", "\\\\").replace("'", "'\"'\"'")
        if initial_command:
            safe_initial = initial_command.replace("\\", "\\\\").replace("'", "'\"'\"'")
            shell_snippet = f"printf '%s\\n' '{safe_prompt}'; {safe_initial}; exec bash"
        elif prompt:
            shell_snippet = f"printf '%s\\n' '{safe_prompt}'; {command_text}; exec bash"
        else:
            shell_snippet = f"{command_text}; exec bash"
        if terminal == "gnome-terminal":
            launch = [terminal, "--title", "HeyGhost Terminal", "--", "bash", "-lc", shell_snippet]
        elif terminal == "qterminal":
            launch = [terminal, "-e", "bash", "-lc", shell_snippet]
        else:
            launch = [terminal, "-title", "HeyGhost Terminal", "-e", "bash", "-lc", shell_snippet] if terminal == "xterm" else [terminal, "-e", "bash", "-lc", shell_snippet]
        try:
            subprocess.Popen(launch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        except OSError as exc:
            self.root.after(0, lambda: self.renderer.handle_debug_event({"event": "error", "text": f"Terminal launch failed: {exc}"}))
            return
        self.root.after(1200, self._remember_active_terminal)

    def _remember_active_terminal(self) -> None:
        window = self._xdotool(["getactivewindow"])
        if window:
            self.last_terminal_window = window.strip().splitlines()[-1]

    def _send_terminal_text(self, text: str, enter: bool, env: dict[str, str]) -> bool:
        if not self._focus_terminal(env):
            return False
        if text:
            try:
                result = subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "1", text], check=False, capture_output=True, text=True, timeout=8, env=env)
            except (OSError, subprocess.SubprocessError):
                return False
            if result.returncode != 0:
                return False
        if enter:
            return self._send_terminal_key("Return", env)
        return True

    def _send_terminal_key(self, key: str, env: dict[str, str]) -> bool:
        mapped = {"ctrl+c": "ctrl+c", "control c": "ctrl+c", "return": "Return", "enter": "Return"}.get(key.lower(), key)
        if not self._focus_terminal(env):
            return False
        try:
            result = subprocess.run(["xdotool", "key", "--clearmodifiers", mapped], check=False, capture_output=True, text=True, timeout=5, env=env)
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    def _focus_terminal(self, env: dict[str, str]) -> bool:
        window = self.last_terminal_window or self._find_terminal_window(env)
        if not window:
            return False
        try:
            result = subprocess.run(["xdotool", "windowactivate", "--sync", window], check=False, capture_output=True, text=True, timeout=5, env=env)
        except (OSError, subprocess.SubprocessError):
            self.last_terminal_window = None
            return False
        if result.returncode == 0:
            self.last_terminal_window = window
            return True
        self.last_terminal_window = None
        return False

    def _find_terminal_window(self, env: dict[str, str]) -> str | None:
        for args in (["search", "--name", "HeyGhost Terminal"], ["search", "--class", "qterminal"], ["search", "--class", "terminal"]):
            window = self._xdotool(args, env)
            if window:
                return window.strip().splitlines()[-1]
        return None

    def _xdotool(self, args: list[str], env: dict[str, str] | None = None) -> str:
        try:
            result = subprocess.run(["xdotool", *args], check=False, capture_output=True, text=True, timeout=5, env=env)
        except (OSError, subprocess.SubprocessError):
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _find_terminal(self) -> str | None:
        for candidate in ("gnome-terminal", "xfce4-terminal", "konsole", "qterminal", "x-terminal-emulator", "xterm"):
            if shutil.which(candidate):
                return candidate
        return None

    def _close_app(self, target: str, env: dict[str, str]) -> None:
        if target == "active":
            subprocess.run(["xdotool", "getactivewindow", "windowclose"], check=False, capture_output=True, text=True, timeout=5, env=env)
            return
        if target == "terminal":
            window = (
                self._xdotool(["search", "--class", "qterminal"], env)
                or self._xdotool(["search", "--class", "terminal"], env)
                or self.last_terminal_window
                or self._find_terminal_window(env)
            )
            if window:
                for item in window.strip().splitlines():
                    try:
                        subprocess.run(["xdotool", "windowclose", item], check=False, capture_output=True, text=True, timeout=2, env=env)
                    except (OSError, subprocess.SubprocessError):
                        pass
            # QTerminal can leave the process alive after WM close in this kiosk flow.
            # A direct process fallback makes the voice command deterministic for demos.
            for pattern in ("qterminal",):
                try:
                    subprocess.run(["pkill", "-f", pattern], check=False, capture_output=True, text=True, timeout=2, env=env)
                except (OSError, subprocess.SubprocessError):
                    pass
            self.last_terminal_window = None
            return
        if target == "browser":
            for klass in ("firefox", "chromium", "google-chrome", "brave-browser"):
                window = self._xdotool(["search", "--class", klass], env)
                if window:
                    subprocess.run(["xdotool", "windowclose", window.strip().splitlines()[-1]], check=False, capture_output=True, text=True, timeout=5, env=env)
                    return


class FuturisticWindow:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.events_path = Path(config.logging.debug_events_file)
        self.offset = 0
        self.root = tk.Tk()
        self.root.title("HeyGhost")
        self.root.configure(bg="#000000")
        self.root.geometry("960x540")
        self.root.minsize(640, 360)

        self.canvas = tk.Canvas(
            self.root,
            bg="#000000",
            bd=0,
            highlightthickness=0,
            cursor="none",
        )
        self.canvas.pack(fill="both", expand=True)
        self.root.bind("<Escape>", lambda _event: self._on_close())
        self.root.bind("<space>", lambda _event: self._trigger())
        self.root.bind("<Return>", lambda _event: self._trigger())
        self.root.bind("<F11>", lambda _event: self._toggle_fullscreen())
        self.root.bind("d", lambda _event: self._toggle_diagnostics())
        self.root.bind("D", lambda _event: self._toggle_diagnostics())
        self.canvas.bind("<Button-1>", lambda _event: self._trigger())

        self.poll_job: str | None = None
        self.status_job: str | None = None
        self.animate_job: str | None = None
        self.hide_job: str | None = None
        self.trigger_busy = False
        self.fullscreen = False
        self.phase = 0
        self.display_text = ""
        self.display_role = "idle"
        self.display_alpha = 0
        self.status_text = "READY"
        self.service_status = "checking"
        self.show_diagnostics = False
        self.diagnostics: dict[str, str] = {}
        self.handled_actions: set[str] = set()
        self.last_terminal_window: str | None = None

        self._load_recent_events()
        self._refresh_service_status()
        self._poll_events()
        self._animate()
        self.root.after(900, self._trigger)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self.root.mainloop()

    def _on_close(self) -> None:
        for job in (self.poll_job, self.status_job, self.animate_job, self.hide_job):
            if job is not None:
                self.root.after_cancel(job)
        self.root.destroy()

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def _toggle_diagnostics(self) -> None:
        self.show_diagnostics = not self.show_diagnostics

    def _animate(self) -> None:
        self.phase = (self.phase + 1) % 360
        self._draw()
        self.animate_job = self.root.after(55, self._animate)

    def _draw(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        portrait = height > width * 1.08
        face_x = width // 2 if portrait else int(width * 0.34)
        face_y = int(height * 0.30) if portrait else height // 2
        text_x = width // 2 if portrait else int(width * 0.70)
        text_y = int(height * 0.72) if portrait else height // 2
        scale = min(width, height)
        pulse = (1 + math.sin(self.phase / 16)) / 2
        self.canvas.delete("all")

        hot_color = self._role_color()
        dim_color = "#12323a" if self.service_status == "active" else "#313840"
        self._draw_background(width, height, hot_color)
        self._draw_face(face_x, face_y, scale, hot_color, dim_color, pulse)
        self._draw_rf_waves(face_x, face_y + int(scale * 0.25), scale, hot_color)

        for idx in range(8):
            y = int(height * (idx + 1) / 9)
            shade = "#031014" if idx % 2 else "#020709"
            self.canvas.create_line(0, y, width, y, fill=shade)

        text = self.display_text
        alpha = self.display_alpha if self.display_text else 0
        if self.display_role == "idle" and self.service_status != "active":
            text = "SERVICE OFFLINE"
            alpha = 190

        box_width = int(width * (0.76 if portrait else 0.44))
        if text:
            font_size = max(18, min(42, box_width // 16))
            color = self._fade_color(hot_color, alpha)
            self.canvas.create_text(
                text_x,
                text_y,
                text=self._wrap_text(text, max(18, box_width // max(10, font_size // 2))),
                fill=color,
                font=("DejaVu Sans Mono", font_size, "bold"),
                justify="center",
                width=box_width,
            )

        status_color = "#0d5f6c" if self.service_status == "active" else "#4f2f2f"
        self.canvas.create_oval(18, height - 28, 30, height - 16, fill=status_color, outline="")
        self.canvas.create_text(
            42,
            height - 22,
            text=self.service_status.upper(),
            fill="#2e8794" if self.service_status == "active" else "#8c5b5b",
            anchor="w",
            font=("DejaVu Sans Mono", 10, "bold"),
        )
        self._draw_branding(width, height)
        if self.show_diagnostics:
            self._draw_diagnostics(width, height)

    def _role_color(self) -> str:
        if self.display_role == "transcribing":
            return "#3cff7a"
        if self.display_role in {"user", "listening"}:
            return "#53d9ff"
        if self.display_role == "thinking":
            return "#2f7cff"
        if self.display_role == "acting":
            return "#7dffb2"
        if self.display_role == "assistant":
            return "#f4fbff"
        if self.service_status != "active":
            return "#6b7480"
        return "#78e6ff"

    def _draw_background(self, width: int, height: int, hot_color: str) -> None:
        self.canvas.create_rectangle(0, 0, width, height, fill="#030508", outline="")
        for idx in range(14):
            x = int((idx * 97 + self.phase * 0.9) % max(1, width))
            y = int((idx * 47 + math.sin((self.phase + idx * 11) / 24) * 14) % max(1, height))
            size = 1 + (idx % 3)
            color = hot_color if idx % 6 == 0 else "#102532"
            self.canvas.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="")
        for idx in range(4):
            y = int((height * (idx + 1) / 5) + math.sin((self.phase + idx * 22) / 30) * 6)
            self.canvas.create_line(
                0,
                y,
                width,
                y,
                fill="#071018",
                width=1,
            )

    def _draw_branding(self, width: int, height: int) -> None:
        font = tkfont.Font(family="DejaVu Sans Mono", size=20, weight="bold")
        segments = (
            ("Ghost", "#ffffff"),
            ("Red", "#ff2d2d"),
            ("Recon", "#ffffff"),
        )
        total_width = sum(font.measure(text) for text, _color in segments)
        x = max(12, (width - total_width) // 2)
        y = height - 25
        for text, color in segments:
            segment_width = font.measure(text)
            self.canvas.create_text(
                x + segment_width // 2,
                y,
                text=text,
                fill=color,
                font=font,
                anchor="center",
            )
            x += segment_width

    def _draw_rf_waves(self, cx: int, cy: int, scale: int, hot_color: str) -> None:
        base = max(16, int(scale * 0.035))
        active = self.service_status == "active"
        if self.display_role == "transcribing":
            color = "#3cff7a"
        elif self.display_role == "thinking":
            color = "#2f7cff"
        elif active:
            color = hot_color
        else:
            color = "#5d6670"

        dot_r = max(3, int(base * 0.22))
        self.canvas.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r, fill=color, outline="")
        sweep = 28 + int(14 * abs(math.sin(self.phase / 14)))
        for idx in range(1, 4):
            r = base * idx + int(3 * math.sin((self.phase + idx * 18) / 11))
            alpha = 220 - idx * 42
            arc_color = self._fade_color(color, alpha)
            self.canvas.create_arc(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                start=40 - sweep,
                extent=sweep,
                outline=arc_color,
                width=2,
                style="arc",
            )
            self.canvas.create_arc(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                start=140,
                extent=sweep,
                outline=arc_color,
                width=2,
                style="arc",
            )

    def _draw_face(
        self,
        cx: int,
        cy: int,
        scale: int,
        hot_color: str,
        dim_color: str,
        pulse: float,
    ) -> None:
        radius = int(scale * (0.17 + pulse * 0.015))
        radius = max(70, min(radius, int(scale * 0.28)))
        mood = self.display_role
        talk = mood == "assistant" and self.display_alpha > 0
        active = self.service_status == "active"
        eye_color = hot_color if active else "#68707a"
        eye_glow = "#baf5ff" if active else "#a7adb5"
        skin = "#111923" if active else "#0b0d10"
        skin_mid = "#182b38" if active else "#11151a"
        skin_light = "#3a5f70" if active else "#1b2026"
        panel_line = "#2b5664" if active else "#303741"
        iris = "#8ff2ff" if active else "#98a1aa"
        cheek = "#214050" if active else "#1a2026"
        head = int(radius * 1.34)
        left = cx - head // 2
        top = cy - int(radius * 0.82)
        right = cx + head // 2
        bottom = top + head

        ring = int(radius * (1.14 + pulse * 0.03))
        for offset, extent, color, line_width in (
            (16, 74, eye_color, 2),
            (128, 48, panel_line, 1),
            (214, 84, eye_color, 2),
        ):
            self.canvas.create_arc(
                cx - ring,
                cy - ring,
                cx + ring,
                cy + ring,
                start=self.phase * (0.9 if talk else 0.45) + offset,
                extent=extent,
                outline=color,
                width=line_width,
                style="arc",
            )

        self.canvas.create_rectangle(
            left - int(radius * 0.08),
            top - int(radius * 0.08),
            right + int(radius * 0.08),
            bottom + int(radius * 0.08),
            fill="#070a0d",
            outline="",
        )
        self.canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill=skin,
            outline=panel_line,
            width=3,
        )
        corner = max(5, int(radius * 0.07))
        for x0, y0, x1, y1 in (
            (left, top, left + corner, top + corner),
            (right - corner, top, right, top + corner),
            (left, bottom - corner, left + corner, bottom),
            (right - corner, bottom - corner, right, bottom),
        ):
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=eye_color, outline="")
        self.canvas.create_rectangle(
            left + int(radius * 0.12),
            top + int(radius * 0.14),
            right - int(radius * 0.12),
            bottom - int(radius * 0.18),
            fill=skin_mid,
            outline=skin_light,
            width=1,
        )
        self.canvas.create_line(
            cx,
            top + int(radius * 0.18),
            cx,
            bottom - int(radius * 0.20),
            fill="#182a33",
            width=1,
        )
        self.canvas.create_line(
            left + int(radius * 0.14),
            top + int(radius * 0.30),
            right - int(radius * 0.14),
            top + int(radius * 0.30),
            fill=panel_line,
            width=1,
        )

        eye_y = cy - int(radius * 0.18)
        eye_dx = int(radius * 0.30)
        eye_w = int(radius * 0.17)
        eye_h = int(radius * 0.075)
        if mood in {"listening", "transcribing", "user"}:
            eye_h = int(radius * 0.09)
        elif mood == "thinking":
            eye_h = int(radius * 0.045)
        elif talk:
            eye_h = int(radius * (0.065 + 0.02 * abs(math.sin(self.phase / 8))))

        gaze = 0
        if mood == "thinking":
            gaze = int(math.sin(self.phase / 20) * radius * 0.035)
        for side in (-1, 1):
            ex = cx + side * eye_dx + gaze
            self.canvas.create_oval(
                ex - int(eye_w * 1.36),
                eye_y - int(eye_h * 1.85),
                ex + int(eye_w * 1.36),
                eye_y + int(eye_h * 1.85),
                fill="#071922",
                outline="",
            )
            self.canvas.create_oval(
                ex - eye_w,
                eye_y - eye_h,
                ex + eye_w,
                eye_y + eye_h,
                fill="#d9f8ff",
                outline=eye_glow,
                width=2,
            )
            iris_r = max(3, int(radius * 0.035))
            self.canvas.create_oval(
                ex - iris_r,
                eye_y - iris_r,
                ex + iris_r,
                eye_y + iris_r,
                fill=iris,
                outline=eye_color,
                width=1,
            )
            self.canvas.create_oval(ex - 2, eye_y - 2, ex + 1, eye_y + 1, fill="#ffffff", outline="")

        brow_y = eye_y - int(radius * 0.18)
        brow_tilt = int(radius * 0.045 if mood in {"thinking", "acting"} else -radius * 0.015 if talk else 0)
        self.canvas.create_line(
            cx - int(radius * 0.45),
            brow_y + brow_tilt,
            cx - int(radius * 0.18),
            brow_y - brow_tilt,
            fill=eye_color,
            width=2,
        )
        self.canvas.create_line(
            cx + int(radius * 0.18),
            brow_y - brow_tilt,
            cx + int(radius * 0.45),
            brow_y + brow_tilt,
            fill=eye_color,
            width=2,
        )

        nose_y = cy + int(radius * 0.10)
        self.canvas.create_line(
            cx,
            eye_y + int(radius * 0.08),
            cx - int(radius * 0.035),
            nose_y,
            fill="#57707a",
            width=1,
        )
        self.canvas.create_line(
            cx - int(radius * 0.035),
            nose_y,
            cx + int(radius * 0.045),
            nose_y + int(radius * 0.02),
            fill="#57707a",
            width=1,
        )
        self.canvas.create_oval(
            cx - int(radius * 0.42),
            cy + int(radius * 0.05),
            cx - int(radius * 0.18),
            cy + int(radius * 0.22),
            fill=cheek,
            outline="",
        )
        self.canvas.create_oval(
            cx + int(radius * 0.18),
            cy + int(radius * 0.05),
            cx + int(radius * 0.42),
            cy + int(radius * 0.22),
            fill=cheek,
            outline="",
        )

        mouth_y = cy + int(radius * 0.38)
        mouth_w = int(radius * 0.30)
        if talk:
            mouth_h = int(radius * (0.035 + 0.055 * abs(math.sin(self.phase / 5))))
            self.canvas.create_oval(
                cx - mouth_w,
                mouth_y - mouth_h,
                cx + mouth_w,
                mouth_y + mouth_h,
                outline=eye_color,
                width=2,
            )
            self.canvas.create_line(
                cx - int(mouth_w * 0.72),
                mouth_y,
                cx + int(mouth_w * 0.72),
                mouth_y,
                fill="#d8f8ff",
                width=1,
            )
        elif mood in {"listening", "transcribing", "user"}:
            self.canvas.create_arc(
                cx - mouth_w,
                mouth_y - int(radius * 0.11),
                cx + mouth_w,
                mouth_y + int(radius * 0.11),
                start=205,
                extent=130,
                outline=eye_color,
                width=2,
                style="arc",
            )
        elif mood == "thinking":
            for idx in range(3):
                dot_x = cx - int(radius * 0.10) + idx * int(radius * 0.10)
                dot_r = 2 + int(2 * abs(math.sin((self.phase + idx * 20) / 12)))
                self.canvas.create_oval(dot_x - dot_r, mouth_y - dot_r, dot_x + dot_r, mouth_y + dot_r, fill=eye_color, outline="")
        else:
            self.canvas.create_line(
                cx - mouth_w,
                mouth_y,
                cx + mouth_w,
                mouth_y,
                fill=eye_color,
                width=2,
            )

        jaw_y = cy + int(radius * 0.72)
        self.canvas.create_arc(
            cx - int(radius * 0.38),
            jaw_y - int(radius * 0.20),
            cx + int(radius * 0.38),
            jaw_y + int(radius * 0.16),
            start=200,
            extent=140,
            outline=panel_line,
            width=1,
            style="arc",
        )

    def _fade_color(self, color: str, alpha: int) -> str:
        alpha = max(0, min(255, alpha))
        r = int(color[1:3], 16) * alpha // 255
        g = int(color[3:5], 16) * alpha // 255
        b = int(color[5:7], 16) * alpha // 255
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_diagnostics(self, width: int, height: int) -> None:
        panel_w = min(420, max(260, int(width * 0.40)))
        panel_h = 188
        x0 = width - panel_w - 18
        y0 = 18
        x1 = width - 18
        y1 = y0 + panel_h
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="#050b10", outline="#295363", width=1)
        lines = [
            ("transcript", self.diagnostics.get("transcript", "")),
            ("corrected", self.diagnostics.get("corrected", "")),
            ("route", self.diagnostics.get("route", "")),
            ("model", self.config.llm.model),
            ("stt", self.diagnostics.get("stt_ms", "")),
            ("llm", self.diagnostics.get("llm_ms", "")),
            ("tts", self.diagnostics.get("tts_ms", "")),
            ("total", self.diagnostics.get("total_ms", "")),
        ]
        y = y0 + 16
        for label, value in lines:
            text = f"{label}: {value}"[:58]
            self.canvas.create_text(
                x0 + 12,
                y,
                text=text,
                fill="#9fd9e8",
                anchor="w",
                font=("DejaVu Sans Mono", 9, "normal"),
            )
            y += 21

    def _wrap_text(self, text: str, width: int) -> str:
        words = text.split()
        lines: list[str] = []
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if len(candidate) > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return "\n".join(lines[:4])

    def _show_message(self, text: str, role: str) -> None:
        self.display_text = text.strip()
        self.display_role = role
        self.display_alpha = 255
        if self.hide_job is not None:
            self.root.after_cancel(self.hide_job)
        self.hide_job = self.root.after(4200 if role == "assistant" else 2600, self._fade_message)

    def _fade_message(self) -> None:
        self.display_alpha -= 22
        if self.display_alpha <= 0:
            self.display_text = ""
            self.display_role = "idle"
            self.display_alpha = 0
            self.hide_job = None
            return
        self.hide_job = self.root.after(35, self._fade_message)

    def _load_recent_events(self) -> None:
        if not self.events_path.exists():
            return
        self.offset = self.events_path.stat().st_size

    def _poll_events(self) -> None:
        if self.events_path.exists():
            size = self.events_path.stat().st_size
            if size < self.offset:
                self.offset = 0
            if size > self.offset:
                with self.events_path.open("r", encoding="utf-8") as handle:
                    handle.seek(self.offset)
                    for line in handle:
                        self._render_event_line(line)
                    self.offset = handle.tell()
        self.poll_job = self.root.after(180, self._poll_events)

    def _render_event_line(self, raw_line: str) -> None:
        try:
            payload = json.loads(raw_line.strip())
        except json.JSONDecodeError:
            return
        event = payload.get("event")
        text = str(payload.get("text", "")).strip()
        if event == "user_text" and text:
            self.diagnostics["transcript"] = text
            self._show_message(text, "user")
        elif event == "assistant_text" and text and text != self.config.assistant.acknowledgement:
            self._show_message(text, "assistant")
        elif event in {"listening", "wake_detected", "session_started"}:
            self.display_text = ""
            self.display_role = "listening"
            self.display_alpha = 180
        elif event == "idle_wake_word":
            self.display_text = ""
            self.display_role = "idle"
            self.display_alpha = 0
        elif event == "transcribing":
            self.display_text = ""
            self.display_role = "transcribing"
            self.display_alpha = 180
        elif event == "thinking":
            self.display_text = "THINKING"
            self.display_role = "thinking"
            self.display_alpha = 180
        elif event == "stt_result":
            self.diagnostics["transcript"] = str(payload.get("text", ""))[:90]
            self.diagnostics["corrected"] = str(payload.get("corrected_text", ""))[:90]
            self.diagnostics["stt_ms"] = str(payload.get("stt_ms", ""))
        elif event == "transcript_corrected":
            self.diagnostics["corrected"] = text
        elif event == "route_selected":
            self.diagnostics["route"] = str(payload.get("route", ""))
        elif event == "llm_result":
            self.diagnostics["model"] = str(payload.get("model", self.config.llm.model))
        elif event == "turn_timing":
            self.diagnostics["stt_ms"] = str(payload.get("stt_ms", ""))
            self.diagnostics["llm_ms"] = str(payload.get("llm_ms", payload.get("response_ms", "")))
            self.diagnostics["tts_ms"] = str(payload.get("tts_ms", ""))
            self.diagnostics["total_ms"] = str(payload.get("total_ms", ""))
        elif event == "speaking":
            self.display_text = "SPEAKING"
            self.display_role = "assistant"
            self.display_alpha = 120
        elif event == "no_speech":
            self.display_text = ""
            self.display_role = "listening"
            self.display_alpha = 135
        elif event == "session_idle":
            self.display_text = ""
            self.display_role = "idle"
            self.display_alpha = 0
        elif event == "action_request":
            self.display_text = "ACTING"
            self.display_role = "acting"
            self.display_alpha = 180
            self._handle_action_request(payload)

    def _refresh_service_status(self) -> None:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", SERVICE_NAME],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            self.service_status = result.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            self.service_status = "unknown"
        self.status_job = self.root.after(2000, self._refresh_service_status)

    def _handle_action_request(self, payload: dict[str, object]) -> None:
        action = payload.get("action")
        if not isinstance(action, dict):
            return
        action_id = self._action_id(payload, action)
        if action_id in self.handled_actions:
            return
        self.handled_actions.add(action_id)
        threading.Thread(target=self._run_desktop_action, args=(action,), daemon=True).start()

    def _action_id(self, payload: dict[str, object], action: dict[str, object]) -> str:
        stamp = str(payload.get("ts", ""))
        kind = str(action.get("kind", ""))
        url = str(action.get("url", ""))
        command = action.get("command")
        command_text = " ".join(command) if isinstance(command, list) else ""
        target = str(action.get("target", ""))
        return f"{stamp}:{kind}:{url}:{target}:{command_text}"

    def _run_desktop_action(self, action: dict[str, object]) -> None:
        kind = str(action.get("kind", ""))
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        if kind in {"browser", "website", "search"}:
            target = str(action.get("url", "about:blank")).strip() or "about:blank"
            subprocess.run(["xdg-open", target], check=False, capture_output=True, text=True, timeout=10, env=env)
            return
        if kind == "linux_app":
            command = action.get("command")
            if isinstance(command, list) and command:
                subprocess.Popen(
                    [str(part) for part in command],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                )
            return
        if kind == "close_app":
            self._close_app(str(action.get("target", "")), env)
            return
        if kind == "terminal":
            prompt = str(action.get("prompt", "HeyGhost terminal ready. Say a command for me to run."))
            self._launch_terminal(["bash"], env, prompt=prompt)
            return
        if kind == "ssh":
            command = action.get("command")
            if isinstance(command, list):
                self._launch_terminal(command, env)
            return
        if kind == "terminal_input":
            text = str(action.get("text", ""))
            enter = bool(action.get("enter", True))
            if not self._send_terminal_text(text, enter, env) and text:
                self._launch_terminal(["bash"], env, initial_command=text)
            return
        if kind == "terminal_key":
            key = str(action.get("key", ""))
            self._send_terminal_key(key, env)

    def _launch_terminal(
        self,
        command: list[str],
        env: dict[str, str],
        prompt: str = "",
        initial_command: str = "",
    ) -> None:
        terminal = self._find_terminal()
        if terminal is None:
            return
        command_text = " ".join(command)
        safe_prompt = prompt.replace("\\", "\\\\").replace("'", "'\"'\"'")
        if initial_command:
            safe_initial = initial_command.replace("\\", "\\\\").replace("'", "'\"'\"'")
            shell_snippet = f"printf '%s\\n' '{safe_prompt}'; {safe_initial}; exec bash"
        elif prompt:
            shell_snippet = f"printf '%s\\n' '{safe_prompt}'; {command_text}; exec bash"
        else:
            shell_snippet = f"{command_text}; exec bash"
        if terminal == "gnome-terminal":
            launch = [terminal, "--title", "HeyGhost Terminal", "--", "bash", "-lc", shell_snippet]
        elif terminal == "qterminal":
            launch = [terminal, "-e", "bash", "-lc", shell_snippet]
        elif terminal == "xterm":
            launch = [terminal, "-title", "HeyGhost Terminal", "-e", "bash", "-lc", shell_snippet]
        else:
            launch = [terminal, "-e", "bash", "-lc", shell_snippet]
        try:
            subprocess.Popen(launch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        except OSError:
            return
        self.root.after(1200, self._remember_active_terminal)

    def _remember_active_terminal(self) -> None:
        window = self._xdotool(["getactivewindow"])
        if window:
            self.last_terminal_window = window.strip().splitlines()[-1]

    def _send_terminal_text(self, text: str, enter: bool, env: dict[str, str]) -> bool:
        if not self._focus_terminal(env):
            return False
        if text:
            try:
                result = subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", "--delay", "1", text],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=8,
                    env=env,
                )
            except (OSError, subprocess.SubprocessError):
                return False
            if result.returncode != 0:
                return False
        if enter:
            return self._send_terminal_key("Return", env)
        return True

    def _send_terminal_key(self, key: str, env: dict[str, str]) -> bool:
        key_map = {
            "ctrl+c": "ctrl+c",
            "control c": "ctrl+c",
            "return": "Return",
            "enter": "Return",
        }
        mapped = key_map.get(key.lower(), key)
        if not self._focus_terminal(env):
            return False
        try:
            result = subprocess.run(
                ["xdotool", "key", "--clearmodifiers", mapped],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    def _focus_terminal(self, env: dict[str, str]) -> bool:
        window = self.last_terminal_window or self._find_terminal_window(env)
        if not window:
            return False
        try:
            result = subprocess.run(
                ["xdotool", "windowactivate", "--sync", window],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
        except (OSError, subprocess.SubprocessError):
            self.last_terminal_window = None
            return False
        if result.returncode == 0:
            self.last_terminal_window = window
            return True
        self.last_terminal_window = None
        return False

    def _find_terminal_window(self, env: dict[str, str]) -> str | None:
        for args in (
            ["search", "--name", "HeyGhost Terminal"],
            ["search", "--class", "qterminal"],
            ["search", "--class", "terminal"],
        ):
            window = self._xdotool(args, env)
            if window:
                return window.strip().splitlines()[-1]
        return None

    def _xdotool(self, args: list[str], env: dict[str, str] | None = None) -> str:
        try:
            result = subprocess.run(
                ["xdotool", *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _find_terminal(self) -> str | None:
        for candidate in ("qterminal", "gnome-terminal", "xfce4-terminal", "konsole", "x-terminal-emulator", "xterm"):
            if shutil.which(candidate):
                resolved = shutil.which(candidate)
                if candidate == "x-terminal-emulator" and resolved:
                    real = os.path.basename(os.path.realpath(resolved))
                    if real:
                        return real
                return candidate
        return None

    def _close_app(self, target: str, env: dict[str, str]) -> None:
        if target == "active":
            subprocess.run(
                ["xdotool", "getactivewindow", "windowclose"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
            return
        if target == "terminal":
            window = (
                self._xdotool(["search", "--class", "qterminal"], env)
                or self._xdotool(["search", "--class", "terminal"], env)
                or self.last_terminal_window
                or self._find_terminal_window(env)
            )
            if window:
                for item in window.strip().splitlines():
                    try:
                        subprocess.run(
                            ["xdotool", "windowclose", item],
                            check=False,
                            capture_output=True,
                            text=True,
                            timeout=2,
                            env=env,
                        )
                    except (OSError, subprocess.SubprocessError):
                        pass
            for pattern in ("qterminal",):
                try:
                    subprocess.run(["pkill", "-f", pattern], check=False, capture_output=True, text=True, timeout=2, env=env)
                except (OSError, subprocess.SubprocessError):
                    pass
            self.last_terminal_window = None
            return
        if target == "browser":
            for klass in ("firefox", "chromium", "google-chrome", "brave-browser"):
                window = self._xdotool(["search", "--class", klass], env)
                if window:
                    subprocess.run(
                        ["xdotool", "windowclose", window.strip().splitlines()[-1]],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        env=env,
                    )
                    return

    def _trigger(self) -> None:
        if self.trigger_busy:
            return
        self.trigger_busy = True
        threading.Thread(target=self._run_trigger, daemon=True).start()

    def _run_trigger(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "heyghost.py"),
                "--config",
                self.config.source_path,
                "trigger",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Trigger failed"
            self.root.after(0, lambda: self._show_message(message, "error"))
        self.root.after(0, self._finish_trigger)

    def _finish_trigger(self) -> None:
        self.trigger_busy = False


class DebugWindow:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.events_path = Path(config.logging.debug_events_file)
        self.offset = 0
        self.root = tk.Tk()
        self.root.title("HeyGhost Console")
        self.root.geometry("860x560")
        self.root.minsize(680, 420)

        self.status_var = tk.StringVar(value="Checking service...")
        self.last_heard_var = tk.StringVar(value="Last heard: -")
        self.last_reply_var = tk.StringVar(value="Last reply: -")
        self.trigger_var = tk.StringVar(value="Ready")
        self.poll_job: str | None = None
        self.status_job: str | None = None
        self.trigger_busy = False
        self.handled_actions: set[str] = set()

        self._build_ui()
        self._load_recent_events()
        self._refresh_service_status()
        self._poll_events()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        top = ttk.Frame(root, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        title = ttk.Label(top, text="HeyGhost Live Console")
        title.grid(row=0, column=0, sticky="w")

        status = ttk.Label(top, textvariable=self.status_var)
        status.grid(row=1, column=0, sticky="w", pady=(6, 0))

        heard = ttk.Label(top, textvariable=self.last_heard_var)
        heard.grid(row=2, column=0, sticky="w", pady=(6, 0))

        reply = ttk.Label(top, textvariable=self.last_reply_var)
        reply.grid(row=3, column=0, sticky="w", pady=(6, 0))

        controls = ttk.Frame(top)
        controls.grid(row=0, column=1, rowspan=4, sticky="e")

        self.trigger_button = ttk.Button(
            controls, text="Trigger", command=self._trigger
        )
        self.trigger_button.grid(row=0, column=0, padx=(0, 8))

        clear_button = ttk.Button(
            controls, text="Clear View", command=self._clear_view
        )
        clear_button.grid(row=0, column=1)

        trigger_state = ttk.Label(top, textvariable=self.trigger_var)
        trigger_state.grid(row=4, column=0, sticky="w", pady=(8, 0))

        frame = ttk.Frame(root, padding=(12, 0, 12, 12))
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.text = tk.Text(
            frame,
            wrap="word",
            state="disabled",
            font=("DejaVu Sans Mono", 11),
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scrollbar.set)

    def _on_close(self) -> None:
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
        if self.status_job is not None:
            self.root.after_cancel(self.status_job)
        self.root.destroy()

    def _clear_view(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._append_line("Console view cleared. New events will continue below.")

    def _append_line(self, line: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", f"{line}\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _load_recent_events(self) -> None:
        if not self.events_path.exists():
            self._append_line("Waiting for HeyGhost debug events...")
            return

        lines = self.events_path.read_text(encoding="utf-8").splitlines()[-80:]
        for line in lines:
            self._render_event_line(line)
        self.offset = self.events_path.stat().st_size

    def _poll_events(self) -> None:
        if not self.events_path.exists():
            self.poll_job = self.root.after(350, self._poll_events)
            return

        size = self.events_path.stat().st_size
        if size < self.offset:
            self.offset = 0

        if size > self.offset:
            with self.events_path.open("r", encoding="utf-8") as handle:
                handle.seek(self.offset)
                for line in handle:
                    self._render_event_line(line)
                self.offset = handle.tell()

        self.poll_job = self.root.after(350, self._poll_events)

    def _render_event_line(self, raw_line: str) -> None:
        raw_line = raw_line.strip()
        if not raw_line:
            return

        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            self._append_line(raw_line)
            return

        line = self._format_event(payload)
        self._append_line(line)

        text = str(payload.get("text", "")).strip()
        event = payload.get("event")
        if event == "user_text" and text:
            self.last_heard_var.set(f"Last heard: {text}")
        elif event == "assistant_text" and text:
            self.last_reply_var.set(f"Last reply: {text}")
        elif event == "action_request":
            self._handle_action_request(payload)
        elif event == "turn_timing":
            record_ms = payload.get("record_ms")
            stt_ms = payload.get("stt_ms")
            response_ms = payload.get("response_ms")
            tts_ms = payload.get("tts_ms")
            source = str(payload.get("source", "")).strip()
            details = (
                f"Timing: record={record_ms}ms stt={stt_ms}ms "
                f"think={response_ms}ms tts={tts_ms}ms"
            )
            if source:
                details = f"{details} source={source}"
            self._append_line(f"{self._format_timestamp(stamp)} {details}")

    def _format_event(self, payload: dict[str, object]) -> str:
        stamp = str(payload.get("ts", ""))
        text = str(payload.get("text", "")).strip()
        event = str(payload.get("event", "event"))
        prefix = self._format_timestamp(stamp)

        if event == "service_started":
            return f"{prefix} Service started"
        if event == "service_stopped":
            return f"{prefix} Service stopped"
        if event == "wake_detected":
            return f"{prefix} Wake detected"
        if event == "listening":
            return f"{prefix} Listening for your question"
        if event == "no_speech":
            return f"{prefix} No speech recognized"
        if event == "user_text":
            return f"{prefix} You: {text}"
        if event == "assistant_text":
            return f"{prefix} Ghost: {text}"
        if event == "action_request":
            return f"{prefix} Action: {text}"
        if event == "error":
            return f"{prefix} Error: {text}"
        return f"{prefix} {event}: {text}" if text else f"{prefix} {event}"

    def _format_timestamp(self, stamp: str) -> str:
        if not stamp:
            return "[--:--:--]"
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("[%H:%M:%S]")
        except ValueError:
            return "[--:--:--]"

    def _refresh_service_status(self) -> None:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", SERVICE_NAME],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            status = result.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            status = "unknown"

        self.status_var.set(f"Service: {status}")
        self.status_job = self.root.after(2000, self._refresh_service_status)

    def _handle_action_request(self, payload: dict[str, object]) -> None:
        action = payload.get("action")
        if not isinstance(action, dict):
            return

        action_id = self._action_id(payload, action)
        if action_id in self.handled_actions:
            return
        self.handled_actions.add(action_id)

        worker = threading.Thread(
            target=self._run_desktop_action,
            args=(action,),
            daemon=True,
        )
        worker.start()

    def _action_id(self, payload: dict[str, object], action: dict[str, object]) -> str:
        stamp = str(payload.get("ts", ""))
        kind = str(action.get("kind", ""))
        url = str(action.get("url", ""))
        command = str(action.get("command", ""))
        target = str(action.get("target", ""))
        return f"{stamp}:{kind}:{url}:{command}:{target}"

    def _run_desktop_action(self, action: dict[str, object]) -> None:
        kind = str(action.get("kind", ""))
        if kind == "browser":
            target = "about:blank"
        elif kind == "website":
            target = str(action.get("url", "")).strip()
        elif kind == "terminal":
            target = "terminal"
        elif kind == "terminal_command":
            target = str(action.get("command", "")).strip()
        elif kind == "ssh":
            target = f"ssh {str(action.get('target', '')).strip()}"
        else:
            self.root.after(0, self._append_line, "[local] Unsupported action request")
            return

        try:
            if kind in {"browser", "website"}:
                result = self._open_url(target)
            else:
                result = self._open_terminal_and_type(
                    command=None if kind == "terminal" else target
                )
        except (OSError, subprocess.SubprocessError) as exc:
            self.root.after(
                0,
                self._append_line,
                f"[local] Failed to open {target}: {exc}",
            )
            return

        if result.returncode == 0:
            if kind == "terminal":
                message = "[local] Opened terminal"
            elif kind == "terminal_command":
                message = f"[local] Opened terminal and typed: {target}"
            elif kind == "ssh":
                message = f"[local] Opened SSH terminal for {target.removeprefix('ssh ').strip()}"
            else:
                message = f"[local] Opened {target}"
            self.root.after(0, self._append_line, message)
            return

        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        self.root.after(
            0,
            self._append_line,
            f"[local] Failed to open {target}: {message}",
        )

    def _open_url(self, target: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        return subprocess.run(
            ["xdg-open", target],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

    def _open_terminal_and_type(
        self, command: str | None
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.setdefault("DISPLAY", os.environ.get("DISPLAY", ":1.0"))
        env.setdefault("XAUTHORITY", os.environ.get("XAUTHORITY", str(Path.home() / ".Xauthority")))

        launcher = shutil.which("qterminal")
        if launcher is None:
            raise FileNotFoundError("qterminal was not found")

        try:
            subprocess.Popen(
                [launcher],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            return subprocess.CompletedProcess([launcher], 1, "", str(exc))

        if command is None:
            return subprocess.CompletedProcess([launcher], 0, "", "")

        window_id = self._wait_for_terminal_window(env)
        if window_id is None:
            return subprocess.CompletedProcess([launcher], 1, "", "Could not find qterminal window")

        typed = self._type_into_window(env, window_id, command)
        if typed.returncode != 0:
            return typed

        return subprocess.CompletedProcess([launcher], 0, "", "")

    def _wait_for_terminal_window(self, env: dict[str, str]) -> str | None:
        searches = (
            ["xdotool", "search", "--sync", "--onlyvisible", "--class", "qterminal"],
            ["xdotool", "search", "--sync", "--onlyvisible", "--name", "qterminal"],
            ["xdotool", "search", "--sync", "--onlyvisible", "--class", "QTerminal"],
            ["xdotool", "search", "--sync", "--onlyvisible", "--name", "QTerminal"],
        )
        for command in searches:
            try:
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=8,
                    env=env,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            window_id = result.stdout.strip().splitlines()[0].strip() if result.stdout.strip() else ""
            if window_id:
                return window_id
        return None

    def _type_into_window(
        self, env: dict[str, str], window_id: str, command: str
    ) -> subprocess.CompletedProcess[str]:
        try:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", window_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
            time.sleep(0.15)
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--delay", "1", "--window", window_id, command],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )
            result = subprocess.run(
                ["xdotool", "key", "--window", window_id, "Return"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return subprocess.CompletedProcess(["xdotool"], 1, "", str(exc))

        return result

    def _trigger(self) -> None:
        if self.trigger_busy:
            return

        self.trigger_busy = True
        self.trigger_button.state(["disabled"])
        self.trigger_var.set("Triggering...")
        self._append_line("[local] Trigger requested")

        worker = threading.Thread(target=self._run_trigger, daemon=True)
        worker.start()

    def _run_trigger(self) -> None:
        try:
            result = subprocess.run(
                [
                    "heyghost",
                    "--config",
                    self.config.source_path,
                    "trigger",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.root.after(0, self._finish_trigger, False, str(exc))
            return

        ok = result.returncode == 0
        message = result.stdout.strip() or result.stderr.strip() or "Trigger failed"
        self.root.after(0, self._finish_trigger, ok, message)

    def _finish_trigger(self, ok: bool, message: str) -> None:
        self.trigger_busy = False
        self.trigger_button.state(["!disabled"])
        self.trigger_var.set("Ready" if ok else "Trigger failed")
        self._append_line(f"[local] {message}")
