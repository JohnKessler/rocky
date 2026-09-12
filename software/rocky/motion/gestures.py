"""Rocky's body language.

A gesture is a list of keyframes - ``(time, pan_offset, tilt_offset)`` in
seconds and degrees - layered on top of wherever the head is already pointing.
Offsets, not absolute positions, so a nod while looking at you stays looking at
you.

Amplitudes are deliberately small. On a head this size, four degrees reads
clearly across a desk; twelve reads like a malfunction.
"""

from __future__ import annotations

from dataclasses import dataclass

from rocky.motion.kinematics import ease_in_out, ease_out_back


@dataclass(frozen=True, slots=True)
class Keyframe:
    t: float
    pan: float
    tilt: float
    easing: str = "smooth"


@dataclass(frozen=True, slots=True)
class GestureDef:
    name: str
    frames: tuple[Keyframe, ...]
    description: str = ""

    @property
    def duration(self) -> float:
        return self.frames[-1].t if self.frames else 0.0

    def sample(self, t: float) -> tuple[float, float]:
        """Offsets at time ``t``, interpolated between keyframes."""
        if not self.frames:
            return 0.0, 0.0
        if t <= self.frames[0].t:
            return self.frames[0].pan, self.frames[0].tilt
        if t >= self.frames[-1].t:
            return self.frames[-1].pan, self.frames[-1].tilt

        for a, b in zip(self.frames, self.frames[1:], strict=False):
            if a.t <= t <= b.t:
                span = b.t - a.t
                u = 0.0 if span <= 0 else (t - a.t) / span
                k = ease_out_back(u) if b.easing == "back" else ease_in_out(u)
                return a.pan + (b.pan - a.pan) * k, a.tilt + (b.tilt - a.tilt) * k
        return self.frames[-1].pan, self.frames[-1].tilt


def _g(
    name: str,
    description: str,
    frames: list[tuple[float, float, float]],
    easing: str = "smooth",
) -> GestureDef:
    return GestureDef(
        name=name,
        description=description,
        frames=tuple(Keyframe(t, p, tl, easing) for t, p, tl in frames),
    )


GESTURES: dict[str, GestureDef] = {
    "nod": _g("nod", "Yes, or I follow you", [
        (0.00, 0, 0), (0.18, 0, -7), (0.36, 0, 3), (0.54, 0, -4), (0.75, 0, 0),
    ]),
    "shake": _g("shake", "No", [
        (0.00, 0, 0), (0.16, -8, 0), (0.34, 8, 0), (0.50, -5, 0), (0.70, 0, 0),
    ]),
    "tilt_curious": _g("tilt_curious", "Head cocked - the question mark", [
        (0.00, 0, 0), (0.30, 5, 4), (1.10, 5, 4), (1.50, 0, 0),
    ]),
    "perk": _g("perk", "Attention caught by something", [
        (0.00, 0, 0), (0.14, 0, 6), (0.40, 0, 4), (0.70, 0, 0),
    ], easing="back"),
    "lean_in": _g("lean_in", "Interested, listening closely", [
        (0.00, 0, 0), (0.45, 0, -3), (1.60, 0, -3), (2.10, 0, 0),
    ]),
    "recoil": _g("recoil", "Startled", [
        (0.00, 0, 0), (0.10, 0, 9), (0.28, -3, 6), (0.80, 0, 0),
    ], easing="back"),
    "scan": _g("scan", "Sweep the room", [
        (0.00, 0, 0), (1.20, -22, 2), (2.60, 22, 2), (3.60, 0, 0),
    ]),
    "shrug": _g("shrug", "I have no idea", [
        (0.00, 0, 0), (0.25, -4, 3), (0.55, 4, 3), (0.90, 0, 0),
    ]),
    "double_take": _g("double_take", "Wait, what?", [
        (0.00, 0, 0), (0.16, 10, 0), (0.32, -2, 0), (0.48, 11, 2), (0.90, 0, 0),
    ], easing="back"),
    "settle": _g("settle", "Relax back to neutral", [
        (0.00, 0, 0), (0.60, 0, -2), (1.20, 0, 0),
    ]),
    "bounce": _g("bounce", "Delight", [
        (0.00, 0, 0), (0.12, 0, 5), (0.26, 0, -2), (0.40, 0, 4), (0.60, 0, 0),
    ], easing="back"),
    "search": _g("search", "Looking for something", [
        (0.00, 0, 0), (0.50, -14, -3), (1.10, 12, -3), (1.60, -6, 0), (2.10, 0, 0),
    ]),
}

#: Names the brain is allowed to pick from, in its tool schema.
GESTURE_NAMES: tuple[str, ...] = tuple(GESTURES)


def get(name: str) -> GestureDef | None:
    return GESTURES.get(name)
