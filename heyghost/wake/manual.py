from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from heyghost.wake.base import WakeWordBackend


class ManualWakeWordBackend(WakeWordBackend):
    def __init__(self, trigger_file: str, poll_interval_ms: int = 250) -> None:
        self.trigger_file = Path(trigger_file)
        self.poll_interval_ms = poll_interval_ms

    def wait_for_wake(self, should_continue: Callable[[], bool]) -> bool:
        while should_continue():
            if self.consume_trigger_file():
                return True
            time.sleep(self.poll_interval_ms / 1000)
        return False

    def consume_trigger_file(self) -> bool:
        if not self.trigger_file.exists():
            return False
        self.trigger_file.unlink(missing_ok=True)
        return True
