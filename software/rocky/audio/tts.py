"""Text to speech, plus the processing that makes it sound like Rocky."""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
import tempfile
import wave
from abc import ABC, abstractmethod
from pathlib import Path

from rocky.audio.devices import pitch_shift, resample
from rocky.config import TtsConfig

log = logging.getLogger(__name__)


class TTS(ABC):
    @abstractmethod
    def synthesize(self, text: str, sample_rate: int) -> list[float]: ...

    def close(self) -> None: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class SilentTTS(TTS):
    """Produces silence of a plausible length.

    Timing still matters with no speech engine installed: the face has to move
    its mouth for the right duration and motion has to gesture in time, so this
    returns the number of samples a real voice would have taken.
    """

    WORDS_PER_MINUTE = 165

    def __init__(self, cfg: TtsConfig) -> None:
        self.cfg = cfg
        self.spoken: list[str] = []

    def synthesize(self, text: str, sample_rate: int) -> list[float]:
        self.spoken.append(text)
        words = max(1, len(text.split()))
        seconds = (words / self.WORDS_PER_MINUTE) * 60.0 / max(0.1, self.cfg.rate)
        return [0.0] * int(seconds * sample_rate)


class SubprocessTTS(TTS):
    """Shared plumbing for engines that write a WAV file."""

    def __init__(self, cfg: TtsConfig) -> None:
        self.cfg = cfg

    def _command(self, text: str, out_path: Path) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    def synthesize(self, text: str, sample_rate: int) -> list[float]:
        if not text.strip():
            return []
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "speech.wav"
            try:
                subprocess.run(
                    self._command(text, out),
                    input=text.encode(),
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            except (subprocess.SubprocessError, OSError) as exc:
                log.error("speech synthesis failed: %s", exc)
                return []
            if not out.exists():
                log.error("speech engine produced no audio")
                return []
            samples, native_rate = _read_wav(out)

        if native_rate != sample_rate and native_rate > 0:
            samples = resample(samples, native_rate / sample_rate)
        return self._voice(samples, sample_rate)

    def _voice(self, samples: list[float], sample_rate: int) -> list[float]:
        """Push the voice away from human.

        Rate first (it changes length), then pitch (which preserves it), then
        the level. Rocky should sound like something using a translator, not
        like a person.
        """
        cfg = self.cfg
        if abs(cfg.rate - 1.0) > 0.01:
            samples = resample(samples, cfg.rate)
        if abs(cfg.pitch_shift) > 0.01:
            samples = pitch_shift(samples, cfg.pitch_shift, sample_rate)
        if abs(cfg.volume - 1.0) > 0.01:
            samples = [v * cfg.volume for v in samples]
        return [max(-1.0, min(1.0, v)) for v in samples]


class PiperTTS(SubprocessTTS):
    """Piper: fast, local, and good enough that Rocky does not need the cloud."""

    def __init__(self, cfg: TtsConfig) -> None:
        super().__init__(cfg)
        self.binary = shutil.which("piper") or shutil.which("piper-tts")
        if not self.binary:
            raise RuntimeError("piper is not on PATH")
        self.voice = _resolve_voice(cfg.voice)
        if not self.voice:
            raise RuntimeError(f"no piper voice model for {cfg.voice!r}")

    def _command(self, text: str, out_path: Path) -> list[str]:
        return [self.binary, "--model", str(self.voice), "--output_file", str(out_path)]


class EspeakTTS(SubprocessTTS):
    """espeak-ng. Robotic in a way that suits Rocky better than it suits most."""

    def __init__(self, cfg: TtsConfig) -> None:
        super().__init__(cfg)
        self.binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.binary:
            raise RuntimeError("espeak-ng is not on PATH")

    def _command(self, text: str, out_path: Path) -> list[str]:
        return [
            self.binary, "-v", "en-gb",
            "-s", str(int(160 * self.cfg.rate)),
            "-p", str(int(max(0, min(99, 40 + self.cfg.pitch_shift * 4)))),
            "-w", str(out_path), text,
        ]


def _resolve_voice(name: str) -> Path | None:
    """Find a piper .onnx voice by name in the usual places."""
    candidates = [
        Path(name),
        Path(f"{name}.onnx"),
        Path.home() / ".local/share/piper/voices" / f"{name}.onnx",
        Path("/usr/share/piper/voices") / f"{name}.onnx",
        Path("var/voices") / f"{name}.onnx",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _read_wav(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        width = wav.getsampwidth()
        channels = wav.getnchannels()
        raw = wav.readframes(wav.getnframes())

    if width != 2:
        log.warning("unexpected sample width %d; treating as silence", width)
        return [], rate

    samples: list[float] = []
    step = 2 * channels
    for i in range(0, len(raw) - step + 1, step):
        value = int.from_bytes(raw[i : i + 2], "little", signed=True)
        samples.append(value / 32768.0)
    return samples, rate


def make_tts(cfg: TtsConfig) -> TTS:
    if cfg.backend == "none":
        return SilentTTS(cfg)
    order = [cfg.backend] + [b for b in ("piper", "espeak") if b != cfg.backend]
    for choice in order:
        try:
            if choice == "piper":
                return PiperTTS(cfg)
            if choice == "espeak":
                return EspeakTTS(cfg)
        except Exception as exc:
            log.info("tts backend %s unavailable: %s", choice, exc)
    log.warning("no speech engine; Rocky will chirp but not talk")
    return SilentTTS(cfg)


def tone(freq: float, seconds: float, sample_rate: int, gain: float = 0.2) -> list[float]:
    """A plain sine, for device tests from the dashboard."""
    n = int(seconds * sample_rate)
    return [math.sin(2 * math.pi * freq * i / sample_rate) * gain for i in range(n)]
