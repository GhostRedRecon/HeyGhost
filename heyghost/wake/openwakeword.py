from __future__ import annotations

from heyghost.wake.base import WakeWordBackend
from heyghost.wake.manual import ManualWakeWordBackend
from heyghost.wake.wake_word import WakeWordDetector


class OpenWakeWordBackend(WakeWordBackend):
    def __init__(
        self,
        trigger_file: str,
        poll_interval_ms: int,
        sample_rate: int,
        input_device: int | None,
        channels: int,
        sensitivity: float,
        model_name: str,
    ) -> None:
        self.detector = WakeWordDetector(
            trigger_file=trigger_file,
            poll_interval_ms=poll_interval_ms,
            sample_rate=sample_rate,
            input_device=input_device,
            channels=channels,
            engine="openwakeword",
            sensitivity=sensitivity,
            model_name=model_name,
        )

    def wait_for_wake(self, should_continue) -> bool:
        return self.detector.wait_for_wake(should_continue)


def build_wake_backend(config, audio_config) -> WakeWordBackend:
    if config.engine == "manual":
        return ManualWakeWordBackend(config.dev_trigger_file, config.poll_interval_ms)
    if config.engine == "always_on":
        return ManualWakeWordBackend(config.dev_trigger_file, config.poll_interval_ms)
    return OpenWakeWordBackend(
        trigger_file=config.dev_trigger_file,
        poll_interval_ms=config.poll_interval_ms,
        sample_rate=audio_config.sample_rate,
        input_device=audio_config.input_device,
        channels=audio_config.channels,
        sensitivity=config.sensitivity,
        model_name=config.model_name,
    )
