"""Wake word detection."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from rocky.audio.vad import VAD, make_vad
from rocky.config import WakeConfig

log = logging.getLogger(__name__)


class WakeDetector(ABC):
    @abstractmethod
    def push(self, frame: list[float], sample_rate: int) -> float:
        """Feed a frame; return 0..1 confidence that the wake word just fired."""

    def reset(self) -> None: ...

    def close(self) -> None: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class NullWake(WakeDetector):
    """Never fires. Pair with ``open_mic`` if you want Rocky always listening."""

    def push(self, frame: list[float], sample_rate: int) -> float:
        return 0.0


class EnergyWake(WakeDetector):
    """No keyword - fires on any sustained speech.

    Useful when Rocky lives on a desk you are alone at, where a wake word is
    just friction. Not appropriate in a shared room: it will answer the
    television.
    """

    def __init__(self, cfg: WakeConfig, vad: VAD | None = None) -> None:
        self.cfg = cfg
        self._vad = vad or make_vad(0.012)
        self._voiced = 0.0

    def push(self, frame: list[float], sample_rate: int) -> float:
        frame_s = len(frame) / sample_rate
        if self._vad.is_speech(frame, sample_rate):
            self._voiced += frame_s
        else:
            self._voiced = max(0.0, self._voiced - frame_s * 2.0)
        if self._voiced > 0.35:
            self._voiced = 0.0
            return 0.9
        return 0.0

    def reset(self) -> None:
        self._voiced = 0.0


class OpenWakeWord(WakeDetector):
    """openWakeWord, which runs comfortably on a Pi 5 CPU."""

    def __init__(self, cfg: WakeConfig) -> None:
        import numpy as np  # noqa: PLC0415
        from openwakeword.model import Model  # noqa: PLC0415

        self.np = np
        self.cfg = cfg
        self._model = Model(wakeword_models=[cfg.model])
        self._pending: list[float] = []
        # openWakeWord expects 80ms chunks of 16kHz 16-bit PCM.
        self._chunk = 1280

    def push(self, frame: list[float], sample_rate: int) -> float:
        self._pending.extend(frame)
        best = 0.0
        while len(self._pending) >= self._chunk:
            chunk = self._pending[: self._chunk]
            del self._pending[: self._chunk]
            pcm = self.np.clip(self.np.asarray(chunk, dtype="float32"), -1, 1)
            scores = self._model.predict((pcm * 32767).astype("int16"))
            best = max(best, max(scores.values(), default=0.0))
        return float(best)

    def reset(self) -> None:
        self._pending.clear()
        try:
            self._model.reset()
        except Exception:  # pragma: no cover - older versions lack reset()
            pass


class DebouncedWake:
    """Wraps a detector with a threshold and a cooldown.

    Without the cooldown one utterance of the wake word fires repeatedly across
    consecutive frames and Rocky interrupts itself.
    """

    def __init__(self, inner: WakeDetector, cfg: WakeConfig) -> None:
        self.inner = inner
        self.cfg = cfg
        self._last_fire = 0.0
        self.last_score = 0.0

    def push(self, frame: list[float], sample_rate: int) -> float | None:
        score = self.inner.push(frame, sample_rate)
        self.last_score = score
        if score < self.cfg.threshold:
            return None
        now = time.time()
        if now - self._last_fire < self.cfg.cooldown_s:
            return None
        self._last_fire = now
        self.inner.reset()
        return score

    @property
    def kind(self) -> str:
        return self.inner.kind


def make_wake(cfg: WakeConfig) -> DebouncedWake:
    if not cfg.enabled or cfg.backend == "none":
        return DebouncedWake(NullWake(), cfg)
    if cfg.backend == "energy":
        return DebouncedWake(EnergyWake(cfg), cfg)
    try:
        return DebouncedWake(OpenWakeWord(cfg), cfg)
    except Exception as exc:
        log.info("openWakeWord unavailable (%s); falling back to speech-triggered wake", exc)
        return DebouncedWake(EnergyWake(cfg), cfg)
