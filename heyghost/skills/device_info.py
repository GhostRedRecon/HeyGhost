from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def memory_summary() -> str:
    meminfo = _read_meminfo()
    total_gib = _kb_to_gib(meminfo.get("MemTotal", 0))
    avail_gib = _kb_to_gib(meminfo.get("MemAvailable", 0))
    used_gib = max(0.0, total_gib - avail_gib)
    return f"RAM: {total_gib:.1f} GiB total, {avail_gib:.1f} available, {used_gib:.1f} in use."


def cpu_summary() -> str:
    cpu_name = _cpu_name()
    cores = os.cpu_count() or 0
    if cpu_name:
        return f"CPU: {cpu_name}, {cores} threads."
    return f"CPU: {cores} threads."


def os_summary() -> str:
    distro = _pretty_os_name()
    kernel = platform.release() or "unknown kernel"
    if distro:
        return f"This system is running {distro} on kernel {kernel}."
    return f"This system is running Linux on kernel {kernel}."


def storage_summary() -> str:
    disk = shutil.disk_usage(Path("/"))
    free_gib = disk.free / (1024 ** 3)
    total_gib = disk.total / (1024 ** 3)
    return (
        f"The root filesystem has {free_gib:.1f} of {total_gib:.1f} gibibytes free."
    )


def system_summary() -> str:
    return f"{memory_summary()} {storage_summary()} {cpu_summary()}"


def _read_meminfo() -> dict[str, int]:
    result: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, _, rest = line.partition(":")
        value = rest.strip().split()[0]
        if value.isdigit():
            result[key] = int(value)
    return result


def _kb_to_gib(value_kb: int) -> float:
    return value_kb / 1024 / 1024


def _pretty_os_name() -> str:
    os_release = Path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.partition("=")[2].strip().strip('"')
    return platform.system().strip()


def _cpu_name() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                _, _, value = line.partition(":")
                return value.strip()
    return platform.processor().strip()
