from __future__ import annotations

import sys
from array import array

from heyghost.audio.vad_silero import SileroVAD
from heyghost.audio.vad_webrtc import WebRTCVAD


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 3, backend: str = "webrtc") -> None:
        self.backend = backend
        self.energy_threshold = 140
        self._vad = None
        if backend == "silero":
            self._vad = SileroVAD(aggressiveness)
        elif backend != "energy":
            self._vad = WebRTCVAD(aggressiveness)

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        if self.backend == "energy":
            return self._energy_is_speech(frame)
        if self._vad is None:
            return False
        return self._vad.is_speech(frame, sample_rate)

    def _energy_is_speech(self, frame: bytes) -> bool:
        samples = array("h")
        samples.frombytes(frame)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return False
        rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
        return rms >= self.energy_threshold
