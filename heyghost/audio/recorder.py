from __future__ import annotations

import sys
import tempfile
import time
import wave
from array import array
from collections import deque
from collections.abc import Callable
from pathlib import Path

from heyghost.audio.input import AudioInput
from heyghost.audio.vad import VoiceActivityDetector


class Recorder:
    def __init__(
        self,
        audio_input: AudioInput,
        vad: VoiceActivityDetector,
        sample_rate: int,
        channels: int,
        frame_duration_ms: int,
        silence_timeout_ms: int,
        min_speech_ms: int,
        max_record_seconds: int,
        preroll_ms: int = 300,
        on_speech_started: Callable[[], None] | None = None,
        on_speech_ended: Callable[[], None] | None = None,
        on_audio_level: Callable[[float], None] | None = None,
    ) -> None:
        self.audio_input = audio_input
        self.vad = vad
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_duration_ms = frame_duration_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.min_speech_ms = min_speech_ms
        self.max_record_seconds = max_record_seconds
        self.preroll_ms = preroll_ms
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        self.max_frames = int((1000 * self.max_record_seconds) / self.frame_duration_ms)
        self.preroll_frames = max(0, self.preroll_ms // self.frame_duration_ms)
        self.on_speech_started = on_speech_started
        self.on_speech_ended = on_speech_ended
        self.on_audio_level = on_audio_level
        self.last_timing: dict[str, float] = {}
        self._last_audio_level_emit = 0.0

    def record_until_silence(self) -> str | None:
        started = time.perf_counter()
        speech_frames: list[bytes] = []
        fallback_frames: list[bytes] = []
        preroll_buffer: deque[bytes] = deque(maxlen=self.preroll_frames)
        silence_frames = 0
        speech_ms = 0
        heard_speech = False
        max_audio_level = 0.0
        fallback_audio_ms = 0
        fallback_level_threshold = 0.012
        silence_limit = max(1, self.silence_timeout_ms // self.frame_duration_ms)

        with self.audio_input.open_stream(blocksize=self.frame_size) as stream:
            for _ in range(self.max_frames):
                frame, overflowed = stream.read(self.frame_size)
                if overflowed:
                    continue

                audio_level = self._audio_level(frame)
                max_audio_level = max(max_audio_level, audio_level)
                self._emit_audio_level(audio_level)
                if audio_level >= fallback_level_threshold:
                    fallback_frames.append(frame)
                    fallback_audio_ms += self.frame_duration_ms
                elif not heard_speech and fallback_frames:
                    fallback_frames.append(frame)

                speech = self.vad.is_speech(frame, self.sample_rate)
                if speech:
                    if not heard_speech and preroll_buffer:
                        speech_frames.extend(preroll_buffer)
                        preroll_buffer.clear()
                    if not heard_speech and self.on_speech_started is not None:
                        self.on_speech_started()
                    heard_speech = True
                    speech_ms += self.frame_duration_ms
                    silence_frames = 0
                    speech_frames.append(frame)
                    continue

                if not heard_speech and self.preroll_frames > 0:
                    preroll_buffer.append(frame)

                if heard_speech:
                    silence_frames += 1
                    speech_frames.append(frame)
                    if silence_frames >= silence_limit:
                        if self.on_speech_ended is not None:
                            self.on_speech_ended()
                        break
        total_ms = (time.perf_counter() - started) * 1000.0
        silence_wait_ms = silence_frames * self.frame_duration_ms if heard_speech else 0
        self.last_timing = {
            "recording_ms": total_ms,
            "speech_ms": float(speech_ms),
            "silence_wait_ms": float(silence_wait_ms),
            "max_audio_level": float(max_audio_level),
            "fallback_audio_ms": float(fallback_audio_ms),
        }

        if not heard_speech or speech_ms < self.min_speech_ms:
            if fallback_audio_ms < self.min_speech_ms or not fallback_frames:
                return None
            speech_frames = fallback_frames
            speech_ms = fallback_audio_ms
            self.last_timing["speech_ms"] = float(speech_ms)
            self.last_timing["fallback_recording"] = 1.0

        fd, output_path = tempfile.mkstemp(prefix="heyghost_input_", suffix=".wav")
        Path(output_path).unlink(missing_ok=True)
        self._write_wav(output_path, speech_frames)
        return output_path


    def _audio_level(self, frame: bytes) -> float:
        samples = array("h")
        samples.frombytes(frame)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return 0.0
        rms = (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
        # Scale quiet laptop microphones into a useful visual range while clipping noise.
        return min(1.0, rms / 6000.0)

    def _emit_audio_level(self, level: float) -> None:
        if self.on_audio_level is None:
            return
        now = time.perf_counter()
        if now - self._last_audio_level_emit < 0.12:
            return
        self._last_audio_level_emit = now
        self.on_audio_level(level)

    def _write_wav(self, path: str, frames: list[bytes]) -> None:
        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(b"".join(frames))
