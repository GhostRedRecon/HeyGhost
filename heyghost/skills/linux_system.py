from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


SAFE_LINUX_APPS: dict[str, tuple[str, ...]] = {
    "terminal": ("terminal", "shell", "bash"),
    "file_manager": ("file manager", "files", "folder", "thunar", "dolphin", "nautilus"),
    "settings": ("settings", "system settings", "control panel"),
    "text_editor": ("text editor", "editor", "mousepad", "gedit", "kate"),
    "calculator": ("calculator", "calc"),
    "browser": ("browser", "web browser", "firefox"),
}

LINUX_TOOL_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("system", ("ls", "cat", "grep", "rg", "find", "ps", "top", "htop", "df", "du", "free", "lscpu", "journalctl", "systemctl")),
    ("network", ("ip", "ss", "ping", "traceroute", "tracepath", "dig", "nslookup", "nmcli", "nmap", "tcpdump", "curl", "wget")),
    ("storage", ("lsblk", "blkid", "fdisk", "parted", "mount", "umount", "smartctl")),
    ("usb and hardware", ("lsusb", "lspci", "lshw", "hwinfo", "dmesg", "udevadm")),
    ("packages", ("apt", "dpkg", "snap", "flatpak", "pip", "pipx")),
    ("security", ("ufw", "nft", "iptables", "fail2ban-client", "ssh", "gpg", "openssl")),
)

APP_COMMANDS: dict[str, list[str]] = {
    "file_manager": ["xdg-open", str(Path.home())],
    "settings": ["xfce4-settings-manager"],
    "text_editor": ["mousepad"],
    "calculator": ["gnome-calculator"],
    "browser": ["xdg-open", "about:blank"],
}


def maybe_linux_skill(text: str) -> tuple[str, str, dict[str, object] | None] | None:
    normalized = _normalize(text)

    app_action = _maybe_open_linux_app(normalized)
    if app_action is not None:
        source, message, action = app_action
        return source, message, action

    if _has_any(normalized, ("nearby wifi", "wifi networks", "wireless networks", "scan wifi", "scan wi fi")):
        return "linux:wifi_scan", wifi_networks_summary(), None

    if _has_any(normalized, ("network devices", "devices on network", "local network devices", "scan network", "wifi devices")):
        return "linux:network_neighbors", network_neighbors_summary(), None

    if _mentions_usb_devices(normalized):
        return "linux:usb_devices", usb_devices_summary(), None

    if _mentions_linux_tools(normalized):
        return "linux:tools", linux_tools_summary(), None

    if _has_any(normalized, ("hardware details", "hardware information", "tell me about this hardware", "device hardware")):
        return "linux:hardware", hardware_summary(), None

    if _has_any(normalized, ("ip address", "network address", "my ip")):
        return "linux:ip_address", ip_address_summary(), None

    return None


def _maybe_open_linux_app(text: str) -> tuple[str, str, dict[str, object]] | None:
    if not _has_any(text, ("open ", "launch ", "start ")):
        return None
    for app_name, aliases in SAFE_LINUX_APPS.items():
        if any(alias in text for alias in aliases):
            if app_name == "terminal":
                return (
                    "linux:open_terminal",
                    "Opening a terminal. What command should I execute?",
                    {"kind": "terminal", "prompt": "HeyGhost terminal ready. Say a command for me to run."},
                )
            command = _resolve_app_command(app_name)
            if command is None:
                return "linux:open_app", f"I do not see an installed launcher for {app_name.replace('_', ' ')}.", {"kind": "noop"}
            return (
                "linux:open_app",
                f"Opening {app_name.replace('_', ' ')}.",
                {"kind": "linux_app", "command": command, "target": app_name},
            )
    return None


def hardware_summary() -> str:
    cpu = _first_cpu_model() or "unknown CPU"
    mem = _read_meminfo()
    total_gib = mem.get("MemTotal", 0) / 1024 / 1024
    kernel = _run_text(["uname", "-r"])
    machine = _run_text(["uname", "-m"])
    return f"This hardware is running {machine or 'Linux'} with {cpu}, about {total_gib:.1f} GiB RAM, and kernel {kernel or 'unknown'}."


def ip_address_summary() -> str:
    output = _run_text(["ip", "-brief", "address"])
    if not output:
        return "I could not read network addresses right now."
    lines = [line for line in output.splitlines() if " lo " not in f" {line} " and "UP" in line]
    if not lines:
        return "I do not see an active non-loopback network interface."
    summary = "; ".join(" ".join(line.split()[:4]) for line in lines[:3])
    return f"Active network interfaces: {summary}."


def network_neighbors_summary() -> str:
    output = _run_text(["ip", "neigh", "show"])
    if not output:
        return "I do not see cached local network neighbors. This is passive; I did not run an aggressive network scan."
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        ip = parts[0]
        dev = parts[2] if len(parts) > 2 and parts[1] == "dev" else "unknown interface"
        mac = ""
        if "lladdr" in parts:
            idx = parts.index("lladdr")
            if idx + 1 < len(parts):
                mac = parts[idx + 1]
        state = parts[-1]
        devices.append(f"{ip} on {dev}" + (f" at {mac}" if mac else "") + f" is {state}")
    if not devices:
        return "I do not see cached local network neighbors."
    return "Known local network neighbors: " + "; ".join(devices[:8]) + "."


def wifi_networks_summary() -> str:
    output = _run_text(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"], timeout=12)
    if not output:
        return "I could not read nearby Wi-Fi networks. NetworkManager or Wi-Fi scanning may not be available."
    networks = []
    seen: set[str] = set()
    for line in output.splitlines():
        ssid, signal, security = _split_nmcli_wifi(line)
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        label = f"{ssid}, signal {signal or 'unknown'}"
        if security:
            label += f", security {security}"
        networks.append(label)
    if not networks:
        return "No nearby Wi-Fi network names were visible."
    return "Nearby Wi-Fi networks: " + "; ".join(networks[:8]) + "."


def usb_devices_summary() -> str:
    output = _run_text(["lsusb"])
    if not output:
        return "I could not read USB devices right now. The lsusb tool may be unavailable or USB information may be inaccessible."

    devices = []
    for line in output.splitlines():
        name = _parse_lsusb_device_name(line)
        if name:
            devices.append(name)

    if not devices:
        return "I do not see any USB devices reported by lsusb."

    count = len(devices)
    listed = "; ".join(devices[:8])
    if count > 8:
        listed += f"; and {count - 8} more"
    return f"USB devices connected: {listed}."


def linux_tools_summary() -> str:
    available_categories = []
    for category, tools in LINUX_TOOL_CATEGORIES:
        installed = [tool for tool in tools if _tool_available(tool)]
        if installed:
            available_categories.append(f"{category}: {', '.join(installed[:8])}")

    if not available_categories:
        return "I could not find common Linux command-line tools in the current PATH."

    return "Installed Linux tools I can see include " + "; ".join(available_categories[:6]) + "."


def _parse_lsusb_device_name(line: str) -> str:
    text = " ".join(line.split())
    if not text:
        return ""
    if " ID " not in text:
        return text
    _, _, after_id = text.partition(" ID ")
    parts = after_id.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return text


def _resolve_app_command(app_name: str) -> list[str] | None:
    command = APP_COMMANDS.get(app_name)
    if not command:
        return None
    executable = command[0]
    if executable == "xdg-open" or shutil.which(executable):
        return command
    alternatives = {
        "text_editor": ("mousepad", "gedit", "kate", "xed"),
        "calculator": ("gnome-calculator", "galculator", "kcalc", "qalculate-gtk"),
        "settings": ("xfce4-settings-manager", "gnome-control-center", "systemsettings"),
    }.get(app_name, ())
    for candidate in alternatives:
        if shutil.which(candidate):
            return [candidate]
    return None


def _split_nmcli_wifi(line: str) -> tuple[str, str, str]:
    parts = re.split(r"(?<!\\):", line)
    parts = [part.replace("\\:", ":").strip() for part in parts]
    while len(parts) < 3:
        parts.append("")
    return parts[0], parts[1], parts[2]


def _first_cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return ""
    for line in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.lower().startswith("model name"):
            return line.partition(":")[2].strip()
    return ""


def _read_meminfo() -> dict[str, int]:
    result: dict[str, int] = {}
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return result
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        key, _, rest = line.partition(":")
        value = rest.strip().split()[0]
        if value.isdigit():
            result[key] = int(value)
    return result


def _run_text(command: list[str], timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _tool_available(name: str) -> bool:
    if shutil.which(name):
        return True
    return False


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9./:@_-]+", " ", text.lower()).strip()


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _mentions_usb_devices(text: str) -> bool:
    return _has_any(
        text,
        (
            "what is connected to usb",
            "what is connected to the usb",
            "what usb devices",
            "usb devices",
            "connected usb",
            "list usb",
            "show usb",
            "usb connected",
        ),
    )


def _mentions_linux_tools(text: str) -> bool:
    return _has_any(
        text,
        (
            "what tools are there in linux",
            "what linux tools",
            "linux tools",
            "available linux tools",
            "installed linux tools",
            "what tools are installed",
            "tool names in linux",
            "command line tools",
        ),
    )
