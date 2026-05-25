import shutil
from pathlib import Path

from . import device_info


def run() -> str:
    disk = shutil.disk_usage(Path("/"))
    free_gb = disk.free / (1024 ** 3)
    total_gb = disk.total / (1024 ** 3)
    return (
        f"System is up. Root disk free space is {free_gb:.1f} of {total_gb:.1f} gigabytes. "
        f"{device_info.memory_summary()}"
    )
