from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk


RISKY_TERMS = (
    " rm ",
    " rm -",
    "mkfs",
    "dd ",
    "wipefs",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "init 0",
    "init 6",
    ":(){",
    "chmod -r",
    "chown -r",
    "systemctl stop",
    "systemctl restart",
    "systemctl disable",
    "apt remove",
    "apt purge",
)


class CommandConsole:
    def __init__(self, root, theme, timeout_seconds: int = 30) -> None:
        self.root = root
        self.theme = theme
        self.timeout_seconds = timeout_seconds
        self.visible = False
        self.running = False
        self.pending_risky_command = ""
        self.frame = tk.Frame(root, bg=theme.colors["panel"], highlightthickness=1, highlightbackground="#1f2937")
        self.output = tk.Text(
            self.frame,
            bg=theme.colors["panel"],
            fg=theme.colors["text_primary"],
            insertbackground=theme.colors["text_primary"],
            relief="flat",
            wrap="word",
            height=8,
            font=(theme.font_family, 10),
        )
        self.entry = tk.Entry(
            self.frame,
            bg="#020617",
            fg=theme.colors["text_primary"],
            insertbackground=theme.colors["text_primary"],
            relief="flat",
            font=(theme.font_family, 11),
        )
        self.output.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        self.entry.pack(fill="x", padx=10, pady=(0, 10))
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Escape>", lambda _event: self.hide())
        self._append("Manual command console. Type a command and press Enter. F10 hides this panel.")

    def toggle(self) -> None:
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        self.visible = True
        self.entry.focus_set()

    def hide(self) -> None:
        self.visible = False
        self.frame.place_forget()

    def render(self, width: int, height: int) -> None:
        if not self.visible:
            return
        panel_w = min(860, max(420, int(width * 0.82)))
        panel_h = min(250, max(180, int(height * 0.36)))
        x = (width - panel_w) // 2
        y = height - panel_h - 24
        self.frame.place(x=x, y=y, width=panel_w, height=panel_h)

    def shutdown(self) -> None:
        self.frame.destroy()

    def _on_enter(self, _event) -> str:
        command = self.entry.get().strip()
        self.entry.delete(0, "end")
        if not command:
            return "break"
        if command.lower() in {"clear", "cls"}:
            self.output.delete("1.0", "end")
            return "break"
        if command.lower() == "confirm" and self.pending_risky_command:
            command = self.pending_risky_command
            self.pending_risky_command = ""
        elif self._looks_risky(command):
            self.pending_risky_command = command
            self._append(f"$ {command}")
            self._append("This command looks risky. Type confirm to run it, or anything else to cancel.")
            return "break"
        elif self.pending_risky_command:
            self.pending_risky_command = ""
            self._append("Canceled pending risky command.")
        self.run_command(command)
        return "break"

    def run_command(self, command: str) -> None:
        if self.running:
            self._append("A command is already running.")
            return
        self.running = True
        self._append(f"$ {command}")
        threading.Thread(target=self._worker, args=(command,), daemon=True).start()

    def _worker(self, command: str) -> None:
        env = os.environ.copy()
        env.setdefault("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        try:
            result = subprocess.run(
                ["bash", "-lc", command],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            code = result.returncode
        except subprocess.TimeoutExpired:
            self.root.after(0, self._finish, f"Command timed out after {self.timeout_seconds} seconds.")
            return
        except OSError as exc:
            self.root.after(0, self._finish, f"Command failed: {exc}")
            return
        parts = []
        if output:
            parts.append(output)
        if error:
            parts.append(error)
        parts.append(f"[exit {code}]")
        self.root.after(0, self._finish, "\n".join(parts))

    def _finish(self, text: str) -> None:
        self._append(text)
        self.running = False
        self.entry.focus_set()

    def _append(self, text: str) -> None:
        self.output.insert("end", f"{text}\n")
        self.output.see("end")

    def _looks_risky(self, command: str) -> bool:
        lowered = f" {command.lower()} "
        return any(term in lowered for term in RISKY_TERMS)
