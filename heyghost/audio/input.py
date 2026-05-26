from __future__ import annotations

import sounddevice as sd


class AudioInput:
    SUPPORTED_SAMPLE_RATES = (48000, 32000, 16000, 8000)

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

    def resolve_sample_rate(self) -> int:
        candidates = []
        for rate in (self.sample_rate, *self.SUPPORTED_SAMPLE_RATES):
            if rate not in candidates:
                candidates.append(rate)

        errors: list[str] = []
        for rate in candidates:
            try:
                sd.check_input_settings(
                    device=self.device,
                    channels=self.channels,
                    dtype="int16",
                    samplerate=rate,
                )
            except Exception as exc:
                errors.append(f"{rate}: {exc}")
                continue
            self.sample_rate = rate
            return rate

        detail = " | ".join(errors) if errors else "no sample rates checked"
        raise RuntimeError(f"No compatible microphone sample rate found. {detail}")

    @staticmethod
    def devices() -> list:
        return sd.query_devices()
