from __future__ import annotations

import subprocess

import sounddevice as sd


class AudioInput:
    SUPPORTED_SAMPLE_RATES = (48000, 32000, 16000, 8000)

    def __init__(self, sample_rate: int, channels: int, device: int | str | None) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.last_opened_device: int | str | None = device

    def open_stream(self, blocksize: int):
        if isinstance(self.device, str):
            self.last_opened_device = self.device
            return ARecordInputStream(
                device=self.device,
                sample_rate=self.sample_rate,
                channels=self.channels,
                blocksize=blocksize,
            )

        errors: list[str] = []
        for device in self._candidate_input_devices():
            try:
                stream = sd.RawInputStream(
                    samplerate=self.sample_rate,
                    blocksize=blocksize,
                    device=device,
                    channels=self.channels,
                    dtype="int16",
                )
            except Exception as exc:
                label = "default" if device is None else str(device)
                errors.append(f"{label}: {exc}")
                continue
            self.last_opened_device = device
            return stream

        detail = " | ".join(errors) if errors else "no input devices found"
        raise RuntimeError(f"Could not open microphone input. {detail}")

    def resolve_sample_rate(self) -> int:
        candidates = []
        for rate in (self.sample_rate, *self.SUPPORTED_SAMPLE_RATES):
            if rate not in candidates:
                candidates.append(rate)

        errors: list[str] = []
        for rate in candidates:
            if isinstance(self.device, str):
                if self._arecord_supports_rate(self.device, rate):
                    self.sample_rate = rate
                    self.last_opened_device = self.device
                    return rate
                errors.append(f"{self.device}@{rate}: arecord failed")
                continue
            for device in self._candidate_input_devices():
                try:
                    sd.check_input_settings(
                        device=device,
                        channels=self.channels,
                        dtype="int16",
                        samplerate=rate,
                    )
                except Exception as exc:
                    label = "default" if device is None else str(device)
                    errors.append(f"{label}@{rate}: {exc}")
                    continue
                self.sample_rate = rate
                self.last_opened_device = device
                return rate

        detail = " | ".join(errors) if errors else "no sample rates checked"
        raise RuntimeError(f"No compatible microphone sample rate found. {detail}")

    @staticmethod
    def devices() -> list:
        return sd.query_devices()

    def _candidate_input_devices(self) -> list[int | None]:
        candidates: list[int | None] = []
        if isinstance(self.device, int):
            candidates.append(self.device)
        candidates.append(None)
        try:
            devices = sd.query_devices()
        except Exception:
            return candidates
        for index, device in enumerate(devices):
            try:
                max_inputs = int(device.get("max_input_channels", 0))
            except Exception:
                continue
            if max_inputs > 0 and index not in candidates:
                candidates.append(index)
        return candidates

    def _arecord_supports_rate(self, device: str, rate: int) -> bool:
        command = [
            "arecord",
            "-q",
            "-D",
            device,
            "-f",
            "S16_LE",
            "-r",
            str(rate),
            "-c",
            str(self.channels),
            "-d",
            "1",
            "-t",
            "raw",
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0


class ARecordInputStream:
    def __init__(self, device: str, sample_rate: int, channels: int, blocksize: int) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.process: subprocess.Popen[bytes] | None = None

    def __enter__(self):
        command = [
            "arecord",
            "-q",
            "-D",
            self.device,
            "-f",
            "S16_LE",
            "-r",
            str(self.sample_rate),
            "-c",
            str(self.channels),
            "-t",
            "raw",
        ]
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return self

    def __exit__(self, *_args) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        self.process = None

    def read(self, frame_count: int) -> tuple[bytes, bool]:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("arecord stream is not open")
        byte_count = frame_count * self.channels * 2
        chunks: list[bytes] = []
        remaining = byte_count
        while remaining > 0:
            chunk = self.process.stdout.read(remaining)
            if not chunk:
                raise RuntimeError("arecord stopped while reading microphone input")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks), False
