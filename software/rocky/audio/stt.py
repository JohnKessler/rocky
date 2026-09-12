"""Speech to text."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from rocky.config import SttConfig

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    confidence: float = 1.0
    duration_s: float = 0.0


class STT(ABC):
    @abstractmethod
    def transcribe(self, samples: list[float], sample_rate: int) -> Transcript: ...

    def close(self) -> None: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class ScriptedSTT(STT):
    """Returns whatever was queued.

    This is how the dashboard's "type to Rocky" box and the tests drive a
    conversation without a microphone - the text enters the pipeline at exactly
    the point a real transcript would.
    """

    def __init__(self) -> None:
        self.queue: list[str] = []
        self.calls = 0

    def say(self, text: str) -> None:
        self.queue.append(text)

    def transcribe(self, samples: list[float], sample_rate: int) -> Transcript:
        self.calls += 1
        text = self.queue.pop(0) if self.queue else ""
        return Transcript(text=text, duration_s=len(samples) / sample_rate)


class FasterWhisperSTT(STT):
    """faster-whisper. ``base.en`` is about the largest model that keeps a
    Pi 5 responsive; ``small.en`` is noticeably better if you can wait."""

    def __init__(self, cfg: SttConfig) -> None:
        from faster_whisper import WhisperModel  # noqa: PLC0415 - optional dependency

        device = cfg.device
        if device == "auto":
            device = "cpu"
        self.cfg = cfg
        self._model = WhisperModel(cfg.model, device=device, compute_type="int8")
        log.info("faster-whisper %s on %s", cfg.model, device)

    def transcribe(self, samples: list[float], sample_rate: int) -> Transcript:
        import numpy as np  # noqa: PLC0415

        audio = np.asarray(samples, dtype="float32")
        segments, info = self._model.transcribe(
            audio,
            language=self.cfg.language or None,
            beam_size=1,          # greedy; the quality difference is small and
                                  # the latency difference is not
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts = [s.text for s in segments]
        text = " ".join(p.strip() for p in parts).strip()
        confidence = float(getattr(info, "language_probability", 1.0) or 1.0)
        return Transcript(text=text, confidence=confidence, duration_s=len(samples) / sample_rate)


def make_stt(cfg: SttConfig) -> STT:
    if cfg.backend == "none":
        return ScriptedSTT()
    try:
        return FasterWhisperSTT(cfg)
    except Exception as exc:
        log.info("faster-whisper unavailable (%s); speech input is scripted only", exc)
        return ScriptedSTT()
