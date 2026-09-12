"""Rocky's voice before words.

In Project Hail Mary, Rocky's language is music - chords, not phonemes - and
speech is a translation layer bolted on afterwards. That is the single most
characterful thing about him, so it is built in here rather than treated as a
sound effect: every utterance is introduced by a motif, and the short
emotional replies are motifs with no words at all.

The motifs are generated, not sampled, so they follow the configured root note
and they can be retuned live from the dashboard.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rocky.config import ChirpConfig

#: Semitone offsets from the root, with relative timing and amplitude.
#: (offset_semitones, start_fraction, length_fraction, gain)
Note = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class Motif:
    name: str
    notes: tuple[Note, ...]
    meaning: str
    duration_scale: float = 1.0


def _chord(*offsets: float, gain: float = 0.8) -> tuple[Note, ...]:
    """All notes together - Rocky's normal way of saying one thing."""
    return tuple((o, 0.0, 1.0, gain) for o in offsets)


def _run(*offsets: float, gain: float = 0.8, overlap: float = 0.35) -> tuple[Note, ...]:
    """Notes in sequence, slightly overlapping, like an arpeggio."""
    n = len(offsets)
    step = 1.0 / n
    return tuple(
        (o, i * step, step * (1.0 + overlap), gain) for i, o in enumerate(offsets)
    )


MOTIFS: dict[str, Motif] = {
    # A perfect fifth and octave: open, unmistakable, Rocky's hello.
    "greeting": Motif("greeting", _run(0, 7, 12), "hello", 1.15),
    "acknowledge": Motif("acknowledge", _chord(0, 7), "I heard you", 0.6),
    "affirm": Motif("affirm", _run(0, 4, 7), "yes", 0.7),
    "deny": Motif("deny", _run(3, 1, 0), "no", 0.8),
    # Rising interval reads as a question in almost every musical tradition.
    "question": Motif("question", _run(0, 5, 10), "question", 0.9),
    "thinking": Motif("thinking", _chord(0, 3, 7, gain=0.4), "working on it", 1.4),
    "delight": Motif("delight", _run(0, 4, 7, 12, 16), "amaze", 1.2),
    "concern": Motif("concern", _run(7, 4, 3), "I do not like this", 1.0),
    "alarm": Motif("alarm", _chord(0, 6, gain=1.0), "bad", 0.55),
    "sad": Motif("sad", _run(7, 3, 0), "sad", 1.3),
    "curious": Motif("curious", _run(0, 2, 7), "what is that", 0.85),
    "goodbye": Motif("goodbye", _run(12, 7, 0), "goodbye", 1.2),
    "laugh": Motif("laugh", _run(7, 12, 7, 12, gain=0.7), "amused", 0.9),
    "agree_strong": Motif("agree_strong", _chord(0, 7, 12, 19), "yes, very", 0.9),
}

MOTIF_NAMES: tuple[str, ...] = tuple(MOTIFS)


def get(name: str) -> Motif | None:
    return MOTIFS.get(name)


def semitone_ratio(semitones: float) -> float:
    return 2.0 ** (semitones / 12.0)


def render(name: str, cfg: ChirpConfig, sample_rate: int = 16000) -> list[float]:
    """Synthesise a motif to mono float samples in -1..1.

    Each note is a small harmonic stack under a soft attack/decay envelope.
    The harmonics are what stop it sounding like a phone notification; the
    envelope is what stops it clicking.
    """
    motif = MOTIFS.get(name)
    if motif is None or not cfg.enabled:
        return []

    duration = max(0.05, cfg.duration_s * motif.duration_scale)
    total = int(duration * sample_rate)
    if total <= 0:
        return []
    out = [0.0] * total

    for offset, start_f, len_f, gain in motif.notes:
        freq = cfg.base_hz * semitone_ratio(offset)
        start = int(start_f * total)
        length = max(1, int(len_f * total))
        end = min(total, start + length)
        if start >= total:
            continue

        for i in range(start, end):
            u = (i - start) / length
            if u >= 1.0:
                break
            # Fast attack, long decay: a struck resonator, not a beep.
            env = min(1.0, u / 0.08) * math.exp(-3.2 * u)
            t = (i - start) / sample_rate
            sample = 0.0
            for h in range(1, cfg.harmonics + 1):
                # Falling harmonic series with a slight inharmonicity, which
                # is what gives it a struck-stone quality rather than an organ.
                sample += math.sin(2 * math.pi * freq * h * (1 + 0.0008 * h) * t) / (h ** 1.7)
            out[i] += sample * env * gain

    # Normalise, then apply the configured level.
    peak = max((abs(v) for v in out), default=0.0)
    if peak > 0:
        scale = cfg.volume / peak
        out = [v * scale for v in out]
    return out


def motif_for_expression(expression: str) -> str | None:
    """The motif that goes with a facial expression, if there is one.

    Rocky chirps and changes face together - they are two views of the same
    feeling, not two separate outputs.
    """
    return {
        "delighted": "delight",
        "happy": "laugh",
        "curious": "curious",
        "thinking": "thinking",
        "concerned": "concern",
        "sad": "sad",
        "alarm": "alarm",
        "surprised": "question",
        "affection": "agree_strong",
        "listening": "acknowledge",
    }.get(expression)
