from __future__ import annotations

import subprocess
import time

from heyghost.audio.output import AudioOutput


class PiperTTS:
    def __init__(
        self,
        binary_path: str,
        model_path: str,
        output_wav_path: str,
        audio_output: AudioOutput,
        length_scale: float = 0.9,
        sentence_silence: float = 0.05,
    ) -> None:
        self.binary_path = binary_path
        self.model_path = model_path
        self.output_wav_path = output_wav_path
        self.audio_output = audio_output
        self.length_scale = length_scale
        self.sentence_silence = sentence_silence

    def speak(self, text: str) -> dict[str, float]:
        command = [
            self.binary_path,
            "--model",
            self.model_path,
            "--output_file",
            self.output_wav_path,
            "--length_scale",
            str(self.length_scale),
            "--sentence_silence",
            str(self.sentence_silence),
            "--quiet",
        ]
        synth_started = time.perf_counter()
        subprocess.run(
            command,
            input=text,
            text=True,
            capture_output=True,
            check=True,
        )
        synthesis_ms = (time.perf_counter() - synth_started) * 1000.0
        playback_ms = self.audio_output.play_wav(self.output_wav_path)
        return {
            "tts_synthesis_ms": synthesis_ms,
            "playback_ms": playback_ms,
            "tts_ms": synthesis_ms + playback_ms,
        }
