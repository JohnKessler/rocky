"""Rocky's face, as numbers.

The face is described by one flat parameter vector. Expressions are named
points in that space and everything in between is a blend, which is what makes
the animation continuous - Rocky never snaps from one drawing to another, it
travels.

Two renderers consume these parameters: the pygame renderer on the display,
and the dashboard's SVG mirror. Because both read the same vector, what you
see in the browser is what is on Rocky's face, not an approximation of it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace


@dataclass(frozen=True, slots=True)
class FaceParams:
    """A complete facial pose.

    Ranges are stated per field; the renderers assume values stay inside them
    but clamp anyway, because a blend that briefly overshoots should not draw
    something broken.
    """

    # eyes
    eye_open_l: float = 1.0       # 0 shut, 1 wide
    eye_open_r: float = 1.0
    eye_arc: float = 0.0          # -1 inner corners up (worried), +1 smiling arc
    eye_squint: float = 0.0       # 0..1, narrows from below
    eye_width: float = 1.0        # 0.6..1.4 horizontal scale
    pupil_x: float = 0.0          # -1..1 gaze offset
    pupil_y: float = 0.0
    pupil_scale: float = 1.0      # 0.5 pinprick .. 1.5 dilated

    # brows - drawn as short strokes above the eyes
    brow_lift: float = 0.0        # -1 lowered, +1 raised
    brow_angle: float = 0.0       # -1 outer-down (sad), +1 inner-down (cross)
    brow_show: float = 0.55       # 0..1 opacity

    # mouth
    mouth_open: float = 0.05      # 0..1
    mouth_curve: float = 0.25     # -1 frown, +1 smile
    mouth_width: float = 1.0      # 0.5..1.5

    # extras
    blush: float = 0.0            # 0..1
    glow: float = 0.35            # 0..1 bloom behind the eyes
    face_tilt: float = 0.0        # -1..1, rolls the whole face
    shake: float = 0.0            # 0..1 jitter amplitude, for alarm

    def blend(self, other: FaceParams, t: float) -> FaceParams:
        """Linear interpolation toward ``other``.

        The endpoints return their operand exactly. ``a + (b - a) * 1.0`` is
        not bit-identical to ``b`` in floating point, and the face driver uses
        equality to decide a cross-fade has finished.
        """
        if t <= 0.0:
            return self
        if t >= 1.0:
            return other
        values = {
            f.name: getattr(self, f.name) + (getattr(other, f.name) - getattr(self, f.name)) * t
            for f in fields(self)
        }
        return FaceParams(**values)

    def with_(self, **overrides: float) -> FaceParams:
        return replace(self, **overrides)

    def to_dict(self) -> dict[str, float]:
        return {k: round(float(v), 4) for k, v in asdict(self).items()}


# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------
# Tuned by eye rather than derived: what matters is that each one is legible at
# arm's length in under half a second, and that neighbouring emotions look
# meaningfully different.

EXPRESSIONS: dict[str, FaceParams] = {
    "neutral": FaceParams(),
    "content": FaceParams(
        eye_arc=0.25, eye_open_l=0.92, eye_open_r=0.92, mouth_curve=0.4,
        mouth_open=0.06, glow=0.4, brow_show=0.4,
    ),
    "happy": FaceParams(
        eye_arc=0.75, eye_open_l=0.7, eye_open_r=0.7, eye_squint=0.3,
        mouth_curve=0.85, mouth_open=0.3, mouth_width=1.15,
        blush=0.25, glow=0.6, brow_lift=0.25,
    ),
    "delighted": FaceParams(
        eye_arc=1.0, eye_open_l=0.45, eye_open_r=0.45, eye_squint=0.55,
        mouth_curve=1.0, mouth_open=0.55, mouth_width=1.3,
        blush=0.5, glow=0.85, brow_lift=0.5, pupil_scale=1.15,
    ),
    "curious": FaceParams(
        eye_open_l=1.0, eye_open_r=0.86, brow_lift=0.6, brow_angle=-0.25,
        pupil_scale=1.2, mouth_open=0.16, mouth_curve=0.2,
        face_tilt=0.35, glow=0.5, brow_show=0.8,
    ),
    "thinking": FaceParams(
        eye_open_l=0.72, eye_open_r=0.72, pupil_x=0.45, pupil_y=-0.35,
        brow_lift=0.2, brow_angle=0.2, mouth_curve=-0.05, mouth_open=0.04,
        mouth_width=0.8, glow=0.3, brow_show=0.7,
    ),
    "listening": FaceParams(
        eye_open_l=1.05, eye_open_r=1.05, pupil_scale=1.12,
        brow_lift=0.3, mouth_open=0.05, mouth_curve=0.25, glow=0.7,
    ),
    "speaking": FaceParams(
        eye_arc=0.3, eye_open_l=0.9, eye_open_r=0.9,
        mouth_open=0.5, mouth_curve=0.35, mouth_width=1.05, glow=0.55,
    ),
    "surprised": FaceParams(
        eye_open_l=1.35, eye_open_r=1.35, pupil_scale=0.75,
        brow_lift=1.0, mouth_open=0.7, mouth_curve=0.0, mouth_width=0.75,
        glow=0.8, brow_show=0.9,
    ),
    "confused": FaceParams(
        eye_open_l=1.1, eye_open_r=0.72, brow_lift=0.45, brow_angle=-0.55,
        mouth_curve=-0.2, mouth_open=0.12, mouth_width=0.85,
        face_tilt=-0.4, brow_show=0.85,
    ),
    "concerned": FaceParams(
        eye_arc=-0.55, eye_open_l=0.95, eye_open_r=0.95,
        brow_lift=0.35, brow_angle=-0.8, mouth_curve=-0.45, mouth_open=0.08,
        glow=0.3, brow_show=0.9,
    ),
    "sad": FaceParams(
        eye_arc=-0.8, eye_open_l=0.6, eye_open_r=0.6, pupil_y=0.35,
        brow_angle=-0.9, brow_lift=0.1, mouth_curve=-0.75, mouth_width=0.8,
        glow=0.18, brow_show=0.8,
    ),
    "sleepy": FaceParams(
        eye_open_l=0.28, eye_open_r=0.24, eye_squint=0.5, pupil_scale=0.85,
        brow_lift=-0.3, mouth_curve=0.1, mouth_open=0.12, mouth_width=0.85,
        glow=0.12, brow_show=0.25,
    ),
    "annoyed": FaceParams(
        eye_open_l=0.62, eye_open_r=0.62, eye_squint=0.6,
        brow_lift=-0.6, brow_angle=0.8, mouth_curve=-0.35, mouth_width=0.8,
        glow=0.35, brow_show=0.95,
    ),
    "focused": FaceParams(
        eye_open_l=0.82, eye_open_r=0.82, eye_squint=0.35, pupil_scale=0.8,
        brow_lift=-0.25, brow_angle=0.3, mouth_curve=0.0, mouth_open=0.03,
        mouth_width=0.8, glow=0.45, brow_show=0.8,
    ),
    "mischief": FaceParams(
        eye_arc=0.5, eye_open_l=0.6, eye_open_r=0.82, eye_squint=0.45,
        brow_lift=0.35, brow_angle=0.45, mouth_curve=0.7, mouth_width=1.2,
        mouth_open=0.2, blush=0.2, glow=0.6, face_tilt=0.25, brow_show=0.9,
    ),
    "affection": FaceParams(
        eye_arc=0.95, eye_open_l=0.5, eye_open_r=0.5, eye_squint=0.5,
        mouth_curve=0.8, mouth_open=0.22, blush=0.75, glow=0.75,
        pupil_scale=1.2, face_tilt=0.15,
    ),
    "alarm": FaceParams(
        eye_open_l=1.4, eye_open_r=1.4, pupil_scale=0.6,
        brow_lift=0.9, brow_angle=-0.3, mouth_open=0.75, mouth_width=0.9,
        mouth_curve=-0.4, glow=1.0, shake=0.6, brow_show=1.0,
    ),
    "blank": FaceParams(
        eye_open_l=0.9, eye_open_r=0.9, mouth_open=0.02, mouth_curve=0.0,
        glow=0.2, brow_show=0.2,
    ),
}

#: The names the brain may choose from.
EXPRESSION_NAMES: tuple[str, ...] = tuple(EXPRESSIONS)


def get(name: str) -> FaceParams | None:
    return EXPRESSIONS.get(name)


def resolve(name: str, intensity: float = 1.0) -> FaceParams:
    """An expression scaled toward neutral.

    Intensity 0.5 is genuinely half as expressive, not a different face, which
    makes 'slightly amused' something the brain can actually ask for.
    """
    target = EXPRESSIONS.get(name)
    if target is None:
        return EXPRESSIONS["neutral"]
    if intensity >= 0.999:
        return target
    return EXPRESSIONS["neutral"].blend(target, max(0.0, intensity))
