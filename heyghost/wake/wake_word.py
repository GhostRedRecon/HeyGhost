from __future__ import annotations

import time
from pathlib import Path
import numpy as np

try:
    from openwakeword import get_pretrained_model_paths
    from openwakeword.model import Model
except Exception:  # pragma: no cover - optional dependency
    Model = None
    get_pretrained_model_paths = None

from heyghost.audio.input import AudioInput


class WakeWordDetector:
    def __init__(
        self,
        trigger_file: str,
        poll_interval_ms: int,
        sample_rate: int = 16000,
        input_device: int | None = None,
        channels: int = 1,
        engine: str = "openwakeword",
        sensitivity: float = 0.5,
        model_name: str = "hey_jarvis",
    ) -> None:
        self.trigger_file = Path(trigger_file)
        self.poll_interval_ms = poll_interval_ms
        self.sample_rate = sample_rate
        self.input_device = input_device
        self.channels = channels
        self.engine = engine
        self.sensitivity = sensitivity
        self.model_name = model_name
        self.audio_input = AudioInput(sample_rate=sample_rate, channels=channels, device=input_device)
        self.model = None

        if self.engine == "openwakeword" and Model is not None and get_pretrained_model_paths is not None:
            model_paths = [path for path in get_pretrained_model_paths() if self.model_name in path]
            if not model_paths:
                model_paths = get_pretrained_model_paths()[:1]
            self.model = Model(wakeword_model_paths=model_paths)
            self.model_name = self._infer_model_name(model_paths[0])

    def wait_for_wake(self, should_continue) -> bool:
        while True:
            if not should_continue():
                return False
            if self._consume_trigger_file():
                return True
            if self.model is not None and self._wait_for_audio_wake(should_continue):
                return True
            time.sleep(self.poll_interval_ms / 1000)

    def _wait_for_audio_wake(self, should_continue) -> bool:
        blocksize = int(self.sample_rate * 0.08)
        if blocksize <= 0:
            blocksize = 1280

        with self.audio_input.open_stream(blocksize=blocksize) as stream:
            while should_continue():
                if self._consume_trigger_file():
                    return True
                data, _overflowed = stream.read(blocksize)
                audio = np.frombuffer(data, dtype=np.int16)
                if audio.size == 0:
                    continue
                if self.channels > 1:
                    try:
                        audio = audio.reshape(-1, self.channels).mean(axis=1).astype(np.int16)
                    except ValueError:
                        continue
                predictions = self.model.predict(audio)
                score = float(predictions.get(self.model_name, 0.0))
                if score >= self.sensitivity:
                    return True
        return False

    def _consume_trigger_file(self) -> bool:
        if not self.trigger_file.exists():
            return False

        self.trigger_file.unlink(missing_ok=True)
        return True

    @staticmethod
    def _infer_model_name(model_path: str) -> str:
        stem = Path(model_path).stem
        for suffix in ("_v0.1", "_v0_1"):
            if stem.endswith(suffix):
                return stem.removesuffix(suffix)
        return stem
