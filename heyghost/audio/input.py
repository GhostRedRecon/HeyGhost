from __future__ import annotations

import sounddevice as sd


class AudioInput:
    def __init__(self, sample_rate: int, channels: int, device: int | None) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device

    def open_stream(self, blocksize: int):
        return sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=blocksize,
            device=self.device,
            channels=self.channels,
            dtype="int16",
        )

    @staticmethod
    def devices() -> list:
        return sd.query_devices()
