from __future__ import annotations

import subprocess
import os
from pathlib import Path

from heyghost.stt.types import Transcript


class WhisperCppSTT:
    def __init__(
        self,
        binary_path: str,
        model_path: str,
        language: str,
        threads: int = 4,
        beam_size: int = 8,
        best_of: int = 8,
        audio_context: int = 0,
        temperature: float = 0.0,
        no_speech_threshold: float = 0.45,
        split_on_word: bool = True,
        suppress_non_speech: bool = True,
        no_fallback: bool = True,
        prompt: str = "",
    ) -> None:
        self.binary_path = binary_path
        self.model_path = model_path
        self.language = language
        self.threads = threads
        self.beam_size = beam_size
        self.best_of = best_of
        self.audio_context = audio_context
        self.temperature = temperature
        self.no_speech_threshold = no_speech_threshold
        self.split_on_word = split_on_word
        self.suppress_non_speech = suppress_non_speech
        self.no_fallback = no_fallback
        self.prompt = prompt

    def transcribe(self, wav_path: str) -> Transcript:
        output_path = Path(wav_path).with_suffix("")
        command = [
            self.binary_path,
            "-m",
            self.model_path,
            "-f",
            wav_path,
            "-l",
            self.language,
            "-t",
            str(self.threads),
            "-bs",
            str(self.beam_size),
            "-bo",
            str(self.best_of),
            "-ac",
            str(self.audio_context),
            "-tp",
            str(self.temperature),
            "-nth",
            str(self.no_speech_threshold),
            "-otxt",
            "-of",
            str(output_path),
        ]
        if self.split_on_word:
            command.append("-sow")
        if self.suppress_non_speech:
            command.append("-sns")
        if self.no_fallback:
            command.append("-nf")
        if self.prompt:
            command.extend(["--prompt", self.prompt])
        env = os.environ.copy()
        install_lib_dir = Path(self.binary_path).resolve().parents[1] / "lib"
        if install_lib_dir.exists():
            current = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = (
                f"{install_lib_dir}:{current}" if current else str(install_lib_dir)
            )
        subprocess.run(command, check=True, capture_output=True, text=True, env=env)

        txt_path = output_path.with_suffix(".txt")
        if not txt_path.exists():
            return Transcript(text="", confidence=0.0, engine="whisper.cpp")
        return Transcript(
            text=txt_path.read_text(encoding="utf-8").strip(),
            confidence=1.0,
            engine="whisper.cpp",
        )
