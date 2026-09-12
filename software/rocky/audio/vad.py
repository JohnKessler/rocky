"""Deciding when someone is talking."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from rocky.audio.devices import rms

log = logging.getLogger(__name__)


class VAD(ABC):
    @abstractmethod
    def is_speech(self, frame: list[float], sample_rate: int) -> bool: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class EnergyVAD(VAD):
    """RMS gate with an adaptive noise floor.

    A fixed threshold works in a quiet room and fails the moment a fan comes
    on, so the floor tracks the quietest recent frames and the gate sits a
    fixed multiple above it. Speech has to be meaningfully louder than the
    room, not louder than some number chosen on a different day.
    """

    def __init__(self, threshold: float = 0.012, margin: float = 3.5) -> None:
        self.threshold = threshold
        self.margin = margin
        self._floor = threshold
        self._warm = 0

    def is_speech(self, frame: list[float], sample_rate: int) -> bool:
        level = rms(frame)
        # Track quiet frames quickly downward and loud ones slowly upward, so
        # a passing truck does not deafen Rocky for the next minute.
        if level < self._floor:
            self._floor += (level - self._floor) * 0.25
        else:
            self._floor += (level - self._floor) * 0.0025
        self._warm = min(self._warm + 1, 100)

        gate = max(self.threshold, self._floor * self.margin)
        return self._warm > 8 and level > gate

    @property
    def noise_floor(self) -> float:
        return self._floor


class WebRtcVAD(VAD):
    """Google's WebRTC VAD - better on speech-shaped noise than raw energy."""

    def __init__(self, aggressiveness: int = 2) -> None:
        import webrtcvad  # noqa: PLC0415 - optional dependency

        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: list[float], sample_rate: int) -> bool:
        # WebRTC only accepts 10/20/30ms of 16-bit PCM at 8/16/32/48kHz.
        pcm = bytearray()
        for v in frame:
            clipped = max(-1.0, min(1.0, v))
            pcm += int(clipped * 32767).to_bytes(2, "little", signed=True)
        try:
            return self._vad.is_speech(bytes(pcm), sample_rate)
        except Exception:
            return False


def make_vad(threshold: float) -> VAD:
    try:
        return WebRtcVAD()
    except Exception as exc:
        log.debug("webrtcvad unavailable (%s); using energy VAD", exc)
        return EnergyVAD(threshold)


class UtteranceGate:
    """Turns a stream of speech/silence decisions into whole utterances.

    Holds through short gaps so a natural pause mid-sentence does not cut the
    sentence in half, and stops at ``max_s`` so a stuck-open microphone cannot
    buffer forever.
    """

    def __init__(self, sample_rate: int, silence_s: float, max_s: float) -> None:
        self.sample_rate = sample_rate
        self.silence_s = silence_s
        self.max_s = max_s
        self._buffer: list[float] = []
        self._silence = 0.0
        self._speaking = False

    def push(self, frame: list[float], is_speech: bool) -> list[float] | None:
        """Feed a frame. Returns the utterance when it ends, else None."""
        frame_s = len(frame) / self.sample_rate

        if is_speech:
            self._speaking = True
            self._silence = 0.0
            self._buffer.extend(frame)
        elif self._speaking:
            self._silence += frame_s
            # Keep the trailing silence: whisper transcribes better with a
            # little room after the last word than with an abrupt cut.
            self._buffer.extend(frame)
            if self._silence >= self.silence_s:
                return self._finish()

        if self.duration >= self.max_s:
            return self._finish()
        return None

    def _finish(self) -> list[float] | None:
        audio = self._buffer
        self._buffer = []
        self._silence = 0.0
        self._speaking = False
        # Anything shorter than a syllable is a cough or a door.
        return audio if len(audio) / self.sample_rate > 0.25 else None

    def reset(self) -> None:
        self._buffer.clear()
        self._silence = 0.0
        self._speaking = False

    @property
    def duration(self) -> float:
        return len(self._buffer) / self.sample_rate

    @property
    def active(self) -> bool:
        return self._speaking
