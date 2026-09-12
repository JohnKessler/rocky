"""Event types carried on the bus.

Topics are dotted strings. Subscribers may use a trailing ``*`` wildcard, so
``motion.*`` sees every motion event. Keeping the payloads as frozen
dataclasses means a subscriber can never mutate another subscriber's copy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

# --- topic constants ---------------------------------------------------------
# Using constants rather than bare strings makes a typo a NameError instead of
# a subscription that silently never fires.

WAKE = "audio.wake"
SPEECH = "audio.speech"
SPEECH_PARTIAL = "audio.speech_partial"
LISTENING = "audio.listening"
SPEAKING = "audio.speaking"
CHIRP = "audio.chirp"

FRAME = "vision.frame"
FACES = "vision.faces"
SCENE = "vision.scene"
MOTION_DETECTED = "vision.motion"

LOOK_AT = "motion.look_at"
GESTURE = "motion.gesture"
POSE = "motion.pose"
MOTION_MODE = "motion.mode"

EXPRESSION = "face.expression"
FACE_FRAME = "face.frame"

UTTERANCE = "brain.utterance"
THOUGHT = "brain.thought"
TOOL_CALL = "brain.tool_call"
BRAIN_STATE = "brain.state"

TELEMETRY = "system.telemetry"
LOG = "system.log"
CONFIG_CHANGED = "system.config_changed"


def _now() -> float:
    return time.time()


@dataclass(frozen=True, slots=True)
class Wake:
    """The wake word fired."""

    keyword: str
    confidence: float
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Speech:
    """A transcript from the speech recogniser."""

    text: str
    final: bool = True
    confidence: float = 1.0
    duration_s: float = 0.0
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Listening:
    """Rocky opened or closed its ears."""

    active: bool
    reason: str = ""
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Speaking:
    """Rocky started or finished talking. Motion uses this to gesture in time,
    and audio capture uses it to avoid transcribing Rocky's own voice."""

    active: bool
    text: str = ""
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Chirp:
    """One of Rocky's musical motifs."""

    motif: str
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Frame:
    """An encoded camera frame, for the dashboard and the brain.

    ``mime`` is carried alongside the bytes because the real camera hands back
    JPEG while the simulator emits PNG, and both the dashboard and the vision
    model need to be told which they are looking at.
    """

    data: bytes
    mime: str
    width: int
    height: int
    seq: int
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Detection:
    """One thing the detector found, in normalised [0, 1] image coordinates."""

    label: str
    cx: float
    cy: float
    w: float
    h: float
    score: float

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass(frozen=True, slots=True)
class Faces:
    """Everything the detector found in one frame."""

    items: tuple[Detection, ...]
    seq: int
    at: float = field(default_factory=_now)

    @property
    def primary(self) -> Detection | None:
        """The face Rocky should be looking at: the biggest one, which is a
        decent proxy for nearest."""
        return max(self.items, key=lambda d: d.area, default=None)


@dataclass(frozen=True, slots=True)
class Scene:
    """A description of what the camera can see, produced periodically."""

    summary: str
    tags: tuple[str, ...] = ()
    notable_change: bool = False
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class LookAt:
    """Point the head somewhere. Coordinates are normalised image space when
    ``frame`` is 'image', or degrees when 'world'."""

    x: float
    y: float
    frame: Literal["image", "world"] = "image"
    priority: int = 0
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Gesture:
    """A named body-language move."""

    name: str
    intensity: float = 1.0
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Pose:
    """Where the head actually is, reported by the motion service."""

    pan: float
    tilt: float
    target_pan: float
    target_tilt: float
    moving: bool
    torque: bool
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Expression:
    """Ask the face for an emotion. ``hold`` is seconds before decaying back
    to the resting expression; 0 means hold until told otherwise."""

    name: str
    intensity: float = 1.0
    hold: float = 0.0
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Utterance:
    """Something Rocky wants to say."""

    text: str
    expression: str | None = None
    gesture: str | None = None
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Record of the brain using one of its tools - surfaced on the dashboard
    so you can see why Rocky did what it did."""

    name: str
    arguments: dict[str, Any]
    result: str = ""
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class BrainState:
    """What the brain is currently doing."""

    state: Literal["idle", "thinking", "speaking", "error"]
    detail: str = ""
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class Telemetry:
    """Periodic health snapshot for the dashboard."""

    data: dict[str, Any]
    at: float = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class LogLine:
    """A log record mirrored onto the bus so the dashboard can show it."""

    level: str
    logger: str
    message: str
    at: float = field(default_factory=_now)
