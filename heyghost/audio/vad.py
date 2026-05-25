from __future__ import annotations

from heyghost.audio.vad_silero import SileroVAD
from heyghost.audio.vad_webrtc import WebRTCVAD


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 3, backend: str = "webrtc") -> None:
        if backend == "silero":
            self._vad = SileroVAD(aggressiveness)
        else:
            self._vad = WebRTCVAD(aggressiveness)

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        return self._vad.is_speech(frame, sample_rate)
