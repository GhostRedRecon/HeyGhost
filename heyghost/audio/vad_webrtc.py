from __future__ import annotations

import webrtcvad


class WebRTCVAD:
    def __init__(self, aggressiveness: int = 3) -> None:
        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        return self._vad.is_speech(frame, sample_rate)
