from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    name: str
    text: str
    action: dict[str, Any] | None = None


def maybe_handle(text: str) -> CommandResult | None:
    normalized = " ".join(text.lower().split())

    if normalized.startswith("run ") or normalized.startswith("execute "):
        command = _build_command(normalized)
        if command is not None:
            output = _run_command(command["argv"])
            return CommandResult(
                "run_command",
                output,
                action={
                    "kind": "terminal_command",
                    "command": command["command"],
                },
            )

    return None


def _build_command(text: str) -> dict[str, object] | None:
    command_text = text.removeprefix("run ").removeprefix("execute ").strip()

    if command_text in {"status", "system status"}:
        return {
            "command": "systemctl status --no-pager hey-ghost.service",
            "argv": ["systemctl", "status", "--no-pager", "hey-ghost.service"],
        }
    if command_text in {"service status", "heyghost status"}:
        return {
            "command": "systemctl status --no-pager hey-ghost.service",
            "argv": ["systemctl", "status", "--no-pager", "hey-ghost.service"],
        }
    if command_text in {"disk usage", "disk space", "filesystem"}:
        return {"command": "df -h /", "argv": ["df", "-h", "/"]}
    if command_text in {"memory", "ram"}:
        return {"command": "free -h", "argv": ["free", "-h"]}
    if command_text in {"cpu", "processor"}:
        return {"command": "lscpu", "argv": ["lscpu"]}
    if command_text in {"hostname", "host name"}:
        return {"command": "hostnamectl", "argv": ["hostnamectl"]}
    if command_text in {"whoami", "user"}:
        return {"command": "whoami", "argv": ["whoami"]}
    if command_text in {"kernel", "uname"}:
        return {"command": "uname -a", "argv": ["uname", "-a"]}
    if command_text in {"ip address", "network", "routes"}:
        return {"command": "ip addr", "argv": ["ip", "addr"]}
    if command_text in {"ip route", "routing table"}:
        return {"command": "ip route", "argv": ["ip", "route"]}
    if command_text in {"processes", "top processes"}:
        return {"command": "ps -ef", "argv": ["ps", "-ef"]}
    if command_text in {"usb devices", "usb"}:
        return {"command": "lsusb", "argv": ["lsusb"]}
    if command_text in {"block devices", "disks", "storage"}:
        return {"command": "lsblk", "argv": ["lsblk"]}
    if command_text in {"uptime"}:
        return {"command": "uptime", "argv": ["uptime"]}
    if command_text in {"mounts", "mounted filesystems"}:
        return {"command": "mount", "argv": ["mount"]}
    if command_text in {"services", "service list"}:
        return {
            "command": "systemctl list-units --type=service --no-pager",
            "argv": ["systemctl", "list-units", "--type=service", "--no-pager"],
        }
    if command_text in {"journal", "logs"}:
        return {
            "command": "journalctl -u hey-ghost.service --no-pager -n 50",
            "argv": ["journalctl", "-u", "hey-ghost.service", "--no-pager", "-n", "50"],
        }

    return None


def _run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"I could not run that command: {exc}"

    output = (result.stdout or result.stderr or "").strip()
    if not output:
        return "The command completed, but it did not return any output."
    lines = output.splitlines()
    if len(lines) > 12:
        return "\n".join(lines[:12]) + "\n...output truncated."
    return output
