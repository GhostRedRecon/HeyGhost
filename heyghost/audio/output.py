from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


class AudioOutput:
    def __init__(self, device: int | None = None) -> None:
        self.device = device

    def play_wav(self, wav_path: str) -> float:
        path = Path(wav_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {wav_path}")

        started = time.perf_counter()
        errors: list[str] = []

        for command, env in self._playback_attempts(str(path)):
            try:
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env,
                )
            except OSError as exc:
                errors.append(f"{command[0]}: {exc}")
                continue
            if result.returncode == 0:
                return (time.perf_counter() - started) * 1000.0
            detail = (result.stderr or result.stdout or "").strip()
            errors.append(f"{' '.join(command)}: {detail or f'exit {result.returncode}'}")

        raise RuntimeError("Audio playback failed. " + " | ".join(errors))

    def _playback_attempts(self, wav_path: str) -> list[tuple[list[str], dict[str, str] | None]]:
        attempts: list[tuple[list[str], dict[str, str] | None]] = []
        if self.device is not None:
            attempts.append((["aplay", "-D", str(self.device), wav_path], None))
        attempts.append((["aplay", wav_path], None))
        if shutil.which("pw-play"):
            for runtime_dir in self._pipewire_runtime_dirs():
                env = os.environ.copy()
                env["XDG_RUNTIME_DIR"] = runtime_dir
                attempts.append((["pw-play", wav_path], env))
        return attempts

    def _pipewire_runtime_dirs(self) -> list[str]:
        candidates = [
            os.environ.get("XDG_RUNTIME_DIR", ""),
            f"/run/user/{os.getuid()}",
            "/run/user/1000",
        ]
        result = []
        for candidate in candidates:
            if (
                candidate
                and candidate not in result
                and Path(candidate, "pipewire-0").exists()
            ):
                result.append(candidate)
        return result
