from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class WakeWordBackend(ABC):
    @abstractmethod
    def wait_for_wake(self, should_continue: Callable[[], bool]) -> bool:
        raise NotImplementedError
