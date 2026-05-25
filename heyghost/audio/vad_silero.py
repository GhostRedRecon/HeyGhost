from __future__ import annotations

from heyghost.audio.vad_webrtc import WebRTCVAD


class SileroVAD:
    """Optional Silero VAD placeholder with WebRTC fallback.

    Silero is intentionally not required by default because torch adds heavy CPU
    and disk cost on the N100. This wrapper keeps the config/backend boundary in
    place and falls back to WebRTC until Silero dependencies are installed and
    wired for streaming frames.
    """

    def __init__(self, aggressiveness: int = 3) -> None:
        self._fallback = WebRTCVAD(aggressiveness)
        self.available = False

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        return self._fallback.is_speech(frame, sample_rate)
