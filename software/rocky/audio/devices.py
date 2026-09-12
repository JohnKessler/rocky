"""Audio input and output."""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class AudioIO(ABC):
    """Mono float32 audio at a fixed sample rate."""

    def __init__(self, sample_rate: int, frame_size: int) -> None:
        self.sample_rate = sample_rate
        self.frame_size = frame_size

    @abstractmethod
    def read(self) -> list[float]:
        """One frame of input. Blocks for at most a frame's worth of time."""

    @abstractmethod
    def play(self, samples: list[float]) -> float:
        """Play samples. Returns the duration in seconds."""

    def close(self) -> None: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class SimAudioIO(AudioIO):
    """Silence in, buffer out.

    Input is quiet room tone rather than digital silence, so the VAD and the
    level meters behave the way they will on real hardware instead of sitting
    at exactly zero.
    """

    def __init__(self, sample_rate: int, frame_size: int) -> None:
        super().__init__(sample_rate, frame_size)
        self.played: list[list[float]] = []
        self.play_seconds = 0.0
        self._phase = 0
        self._injected: list[float] = []

    def inject(self, samples: list[float]) -> None:
        """Queue samples to be returned by :meth:`read`, for tests."""
        self._injected.extend(samples)

    def read(self) -> list[float]:
        if self._injected:
            frame = self._injected[: self.frame_size]
            del self._injected[: self.frame_size]
            if len(frame) < self.frame_size:
                frame += [0.0] * (self.frame_size - len(frame))
            return frame
        # Very low-level pink-ish noise stands in for room tone.
        out = []
        for _ in range(self.frame_size):
            self._phase += 1
            out.append(math.sin(self._phase * 0.0007) * 0.0015)
        return out

    def play(self, samples: list[float]) -> float:
        self.played.append(list(samples))
        duration = len(samples) / self.sample_rate
        self.play_seconds += duration
        return duration


class SoundDeviceIO(AudioIO):
    """PortAudio, which is what ALSA looks like from Python."""

    def __init__(
        self,
        sample_rate: int,
        frame_size: int,
        input_device: str = "",
        output_device: str = "",
    ) -> None:
        super().__init__(sample_rate, frame_size)
        import sounddevice as sd  # noqa: PLC0415 - optional hardware dependency

        self.sd = sd
        self._in_device = _find_device(sd, input_device, want_input=True)
        self._out_device = _find_device(sd, output_device, want_input=False)

        self._stream = sd.InputStream(
            samplerate=sample_rate, blocksize=frame_size, channels=1,
            dtype="float32", device=self._in_device,
        )
        self._stream.start()
        log.info("audio in=%s out=%s @%dHz", self._in_device, self._out_device, sample_rate)

    def read(self) -> list[float]:
        data, overflowed = self._stream.read(self.frame_size)
        if overflowed:
            log.debug("input overflow - a frame was dropped")
        return [float(v) for v in data[:, 0]]

    def play(self, samples: list[float]) -> float:
        import numpy as np  # noqa: PLC0415

        array = np.asarray(samples, dtype="float32")
        self.sd.play(array, samplerate=self.sample_rate, device=self._out_device)
        self.sd.wait()
        return len(samples) / self.sample_rate

    def close(self) -> None:
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:  # pragma: no cover
            pass


def _find_device(sd, fragment: str, *, want_input: bool):
    """Match a device by name fragment, so config survives reboots.

    ALSA device indices shuffle when USB devices enumerate in a different
    order; matching on a name fragment means "the ReSpeaker" keeps meaning the
    ReSpeaker.
    """
    if not fragment:
        return None
    needle = fragment.lower()
    for index, info in enumerate(sd.query_devices()):
        channels = info["max_input_channels"] if want_input else info["max_output_channels"]
        if channels > 0 and needle in info["name"].lower():
            return index
    log.warning("no audio device matching %r; using the default", fragment)
    return None


def make_audio_io(
    preference: str, sample_rate: int, frame_size: int,
    input_device: str = "", output_device: str = "",
) -> AudioIO:
    if preference == "sim":
        return SimAudioIO(sample_rate, frame_size)
    try:
        return SoundDeviceIO(sample_rate, frame_size, input_device, output_device)
    except Exception as exc:
        if preference == "sounddevice":
            raise
        log.info("No audio device (%s); running audio in simulation", exc)
        return SimAudioIO(sample_rate, frame_size)


def rms(frame: list[float]) -> float:
    if not frame:
        return 0.0
    return math.sqrt(sum(v * v for v in frame) / len(frame))


def resample(samples: list[float], factor: float) -> list[float]:
    """Linear resample. Used for pitch shifting, where quality matters less
    than not pulling in a DSP dependency for one effect."""
    if factor == 1.0 or not samples:
        return list(samples)
    out_len = max(1, int(len(samples) / factor))
    out = []
    for i in range(out_len):
        src = i * factor
        j = int(src)
        frac = src - j
        a = samples[min(j, len(samples) - 1)]
        b = samples[min(j + 1, len(samples) - 1)]
        out.append(a + (b - a) * frac)
    return out


def pitch_shift(samples: list[float], semitones: float, sample_rate: int) -> list[float]:
    """Shift pitch while keeping the duration roughly intact.

    Resample to move the pitch, then patch the length back with overlapping
    grains. Crude, but on a voice already being pushed away from human it is
    exactly the kind of crude that helps.
    """
    if abs(semitones) < 0.01 or not samples:
        return list(samples)
    ratio = 2.0 ** (semitones / 12.0)
    shifted = resample(samples, 1.0 / ratio)
    target = len(samples)
    if len(shifted) == target:
        return shifted
    if len(shifted) > target:
        return shifted[:target]

    out = list(shifted)
    grain = max(1, sample_rate // 40)
    while len(out) < target:
        take = min(grain, target - len(out), len(shifted))
        start = max(0, len(shifted) - take)
        out.extend(shifted[start : start + take])
    return out[:target]


def now_ms() -> float:
    return time.perf_counter() * 1000.0
