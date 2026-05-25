from __future__ import annotations

import json
import wave

from heyghost.stt.types import Transcript


class VoskSTT:
    def __init__(self, model_path: str, sample_rate: int = 16000) -> None:
        from vosk import KaldiRecognizer, Model

        self.model_path = model_path
        self.sample_rate = sample_rate
        self._model = Model(model_path)
        self._recognizer_type = KaldiRecognizer

    def transcribe(self, wav_path: str) -> Transcript:
        recognizer = self._recognizer_type(self._model, self.sample_rate)
        recognizer.SetWords(True)
        chunks: list[str] = []
        confidences: list[float] = []

        with wave.open(wav_path, "rb") as wav_file:
            while True:
                data = wav_file.readframes(4000)
                if not data:
                    break
                if recognizer.AcceptWaveform(data):
                    self._consume_result(recognizer.Result(), chunks, confidences)

        self._consume_result(recognizer.FinalResult(), chunks, confidences)
        text = " ".join(chunk for chunk in chunks if chunk).strip()
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return Transcript(text=text, confidence=confidence, engine="vosk")

    def _consume_result(
        self,
        raw: str,
        chunks: list[str],
        confidences: list[float],
    ) -> None:
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            return
        text = str(result.get("text", "")).strip()
        if text:
            chunks.append(text)
        for word in result.get("result", []) or []:
            if isinstance(word, dict) and "conf" in word:
                try:
                    confidences.append(float(word["conf"]))
                except (TypeError, ValueError):
                    pass
