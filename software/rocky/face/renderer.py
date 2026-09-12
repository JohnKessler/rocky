"""Drawing the face.

The geometry lives in :func:`layout`, which is pure and therefore testable. The
pygame renderer only turns those shapes into pixels, and the dashboard mirrors
the same maths in JavaScript. If you change how Rocky looks, change ``layout``
and both renderers follow.
"""

from __future__ import annotations

import logging
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from rocky.config import FaceConfig
from rocky.face.expressions import FaceParams

log = logging.getLogger(__name__)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class EyeShape:
    cx: float
    cy: float
    rx: float
    ry: float
    lid_top: float      # how far the upper lid covers, in pixels
    lid_bottom: float
    arc: float          # -1..1, curvature of the lower lid
    pupil_cx: float
    pupil_cy: float
    pupil_r: float


@dataclass
class Layout:
    """Everything needed to paint one frame, in pixels."""

    width: int
    height: int
    left: EyeShape
    right: EyeShape
    brow_left: tuple[tuple[float, float], tuple[float, float]]
    brow_right: tuple[tuple[float, float], tuple[float, float]]
    brow_alpha: float
    brow_thickness: float
    mouth_cx: float
    mouth_cy: float
    mouth_w: float
    mouth_h: float
    mouth_curve: float
    blush: float
    glow: float
    tilt_rad: float
    jitter: tuple[float, float]


def layout(p: FaceParams, cfg: FaceConfig, *, t: float = 0.0) -> Layout:
    """Turn a parameter vector into drawable geometry.

    Kept free of any drawing library so it can be unit tested and so the
    dashboard can reproduce it exactly.
    """
    w, h = cfg.width, cfg.height
    short = min(w, h)

    spacing = cfg.eye_spacing * w
    eye_r = cfg.eye_radius * short
    eye_y = cfg.eye_y * h
    cx = w / 2.0

    jitter = (0.0, 0.0)
    if p.shake > 0.01:
        amp = p.shake * short * 0.012
        jitter = (
            math.sin(t * 47.0) * amp,
            math.cos(t * 39.0) * amp * 0.6,
        )

    def eye(sign: int, openness: float) -> EyeShape:
        rx = eye_r * _clamp(p.eye_width, 0.5, 1.6)
        ry = eye_r * _clamp(openness, 0.0, 1.6)
        ex = cx + sign * spacing / 2.0
        # Lids: the top one closes for blinks, the bottom one for squints.
        lid_top = ry * (1.0 - _clamp(openness, 0.0, 1.0)) * 0.0
        lid_bottom = ry * _clamp(p.eye_squint, 0.0, 1.0) * 0.55
        pupil_r = eye_r * 0.44 * _clamp(p.pupil_scale, 0.35, 1.8)
        # The pupil travels inside the eye, never outside it.
        travel_x = max(0.0, rx - pupil_r - short * 0.006)
        travel_y = max(0.0, ry - pupil_r - short * 0.006)
        return EyeShape(
            cx=ex, cy=eye_y, rx=rx, ry=ry,
            lid_top=lid_top, lid_bottom=lid_bottom, arc=p.eye_arc,
            pupil_cx=ex + _clamp(p.pupil_x, -1, 1) * travel_x,
            pupil_cy=eye_y + _clamp(p.pupil_y, -1, 1) * travel_y,
            pupil_r=pupil_r,
        )

    left = eye(-1, p.eye_open_l)
    right = eye(+1, p.eye_open_r)

    # Brows sit above each eye; angle rotates them about their midpoint.
    brow_gap = eye_r * (1.35 - p.brow_lift * 0.42)
    brow_len = eye_r * 1.5
    brow_dy = eye_r * 0.34

    def brow(e: EyeShape, sign: int) -> tuple[tuple[float, float], tuple[float, float]]:
        y = e.cy - brow_gap
        inner_x = e.cx - sign * brow_len / 2.0
        outer_x = e.cx + sign * brow_len / 2.0
        inner_y = y + p.brow_angle * brow_dy
        outer_y = y - p.brow_angle * brow_dy * 0.55
        return ((inner_x, inner_y), (outer_x, outer_y))

    mouth_w = short * 0.22 * _clamp(p.mouth_width, 0.4, 1.8)
    mouth_h = short * 0.075 * _clamp(p.mouth_open, 0.0, 1.2) + short * 0.008

    return Layout(
        width=w, height=h,
        left=left, right=right,
        brow_left=brow(left, -1), brow_right=brow(right, +1),
        brow_alpha=_clamp(p.brow_show, 0.0, 1.0),
        brow_thickness=max(2.0, eye_r * 0.16),
        mouth_cx=cx, mouth_cy=eye_y + short * 0.27,
        mouth_w=mouth_w, mouth_h=mouth_h,
        mouth_curve=_clamp(p.mouth_curve, -1.0, 1.0),
        blush=_clamp(p.blush, 0.0, 1.0),
        glow=_clamp(p.glow, 0.0, 1.0),
        tilt_rad=math.radians(_clamp(p.face_tilt, -1, 1) * 9.0),
        jitter=jitter,
    )


class FaceRenderer(ABC):
    """Paints a :class:`FaceParams` somewhere."""

    @abstractmethod
    def draw(self, params: FaceParams, t: float) -> None: ...

    def close(self) -> None: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class HeadlessRenderer(FaceRenderer):
    """Draws nothing, remembers everything.

    Used on a laptop and in tests. The dashboard still shows a live face,
    because it renders from the same parameters over the websocket.
    """

    def __init__(self) -> None:
        self.last: FaceParams | None = None
        self.frames = 0

    def draw(self, params: FaceParams, t: float) -> None:
        self.last = params
        self.frames += 1


class PygameRenderer(FaceRenderer):
    """Fullscreen SDL renderer for the round panel on Rocky's face."""

    def __init__(self, cfg: FaceConfig) -> None:
        import pygame  # noqa: PLC0415 - optional hardware dependency

        self.pygame = pygame
        self.cfg = cfg
        pygame.init()
        pygame.mouse.set_visible(False)
        flags = pygame.FULLSCREEN | pygame.SCALED if cfg.fullscreen else 0
        self.screen = pygame.display.set_mode((cfg.width, cfg.height), flags)
        pygame.display.set_caption("Rocky")
        self.surface = pygame.Surface((cfg.width, cfg.height), pygame.SRCALPHA)
        self.glow_surface = pygame.Surface((cfg.width, cfg.height), pygame.SRCALPHA)
        self.eye_layer = pygame.Surface((cfg.width, cfg.height), pygame.SRCALPHA)
        self._mask = self._build_mask() if cfg.circular_mask else None
        log.info("pygame display %dx%d", cfg.width, cfg.height)

    def _build_mask(self):
        """Black corners, so a round panel does not show square artwork."""
        pygame = self.pygame
        cfg = self.cfg
        mask = pygame.Surface((cfg.width, cfg.height), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 255))
        pygame.draw.circle(
            mask, (0, 0, 0, 0),
            (cfg.width // 2, cfg.height // 2),
            min(cfg.width, cfg.height) // 2,
        )
        return mask

    # -- painting -----------------------------------------------------------

    def draw(self, params: FaceParams, t: float) -> None:
        pygame = self.pygame
        cfg = self.cfg
        pal = cfg.palette
        geo = layout(params, cfg, t=t)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt

        self.surface.fill(_rgb(pal.background))
        self.glow_surface.fill((0, 0, 0, 0))

        dx, dy = geo.jitter

        if geo.glow > 0.02:
            glow_col = (*_rgb(pal.glow), int(90 * geo.glow))
            for eye in (geo.left, geo.right):
                pygame.draw.ellipse(
                    self.glow_surface, glow_col,
                    pygame.Rect(
                        eye.cx - eye.rx * 2.2 + dx, eye.cy - eye.ry * 2.2 + dy,
                        eye.rx * 4.4, eye.ry * 4.4,
                    ),
                )
            self.surface.blit(self.glow_surface, (0, 0))

        if geo.blush > 0.02:
            blush_col = (*_rgb(pal.blush), int(70 * geo.blush))
            for eye in (geo.left, geo.right):
                pygame.draw.ellipse(
                    self.glow_surface, blush_col,
                    pygame.Rect(
                        eye.cx - eye.rx * 1.1 + dx, eye.cy + eye.ry * 1.25 + dy,
                        eye.rx * 2.2, eye.ry * 0.9,
                    ),
                )
            self.surface.blit(self.glow_surface, (0, 0))

        # The eyes live on their own transparent layer so their lids can
        # erase, leaving the glow behind them untouched.
        self.eye_layer.fill((0, 0, 0, 0))
        for eye in (geo.left, geo.right):
            self._draw_eye(self.eye_layer, eye, dx, dy)
        self.surface.blit(self.eye_layer, (0, 0))

        if geo.brow_alpha > 0.03:
            col = (*_rgb(pal.iris), int(255 * geo.brow_alpha))
            for (a, b) in (geo.brow_left, geo.brow_right):
                pygame.draw.line(
                    self.surface, col,
                    (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy),
                    int(geo.brow_thickness),
                )

        self._draw_mouth(geo, dx, dy)

        frame = self.surface
        if abs(geo.tilt_rad) > 0.002:
            frame = pygame.transform.rotate(frame, math.degrees(-geo.tilt_rad))

        self.screen.fill(_rgb(pal.background))
        rect = frame.get_rect(center=(cfg.width // 2, cfg.height // 2))
        self.screen.blit(frame, rect)
        if self._mask is not None:
            self.screen.blit(self._mask, (0, 0))
        pygame.display.flip()

    def _draw_eye(self, surface, eye: EyeShape, dx: float, dy: float) -> None:
        """Paint one eye onto a transparent layer.

        The lids erase rather than overpaint. Painting them in the background
        colour looks right on a flat backdrop and wrong the moment there is a
        glow behind the eye - it stamps a visible block out of it.
        """
        pygame = self.pygame
        pal = self.cfg.palette
        erase = (0, 0, 0, 0)

        if eye.ry < 1.5:
            pygame.draw.line(
                surface, _rgb(pal.iris),
                (eye.cx - eye.rx + dx, eye.cy + dy), (eye.cx + eye.rx + dx, eye.cy + dy),
                max(2, int(eye.rx * 0.13)),
            )
            return

        rect = pygame.Rect(
            eye.cx - eye.rx + dx, eye.cy - eye.ry + dy, eye.rx * 2, eye.ry * 2
        )
        pygame.draw.ellipse(surface, _rgb(pal.iris), rect)
        pygame.draw.circle(
            surface, _rgb(pal.iris_inner),
            (int(eye.pupil_cx + dx), int(eye.pupil_cy + dy)), int(eye.pupil_r),
        )
        # Catchlight - small, offset, and the single cheapest thing that makes
        # an eye look alive rather than printed.
        pygame.draw.circle(
            surface, (255, 255, 255),
            (int(eye.pupil_cx + eye.pupil_r * 0.35 + dx),
             int(eye.pupil_cy - eye.pupil_r * 0.4 + dy)),
            max(1, int(eye.pupil_r * 0.22)),
        )

        left = eye.cx - eye.rx - 3 + dx
        right = eye.cx + eye.rx + 3 + dx

        if eye.arc > 0.02:
            # Smiling eyes. The lid eats upward from the bottom in proportion
            # to arc; the factor is capped so a sliver of eye survives at
            # arc = 1, or a delighted Rocky has no eyes at all.
            base = eye.cy + eye.ry * (1.0 - 1.55 * eye.arc) + dy
            bulge = eye.ry * eye.arc * 0.5
            points = [(left, eye.cy + eye.ry + 4 + dy)]
            steps = 16
            for i in range(steps + 1):
                u = i / steps
                points.append((left + (right - left) * u, base - bulge * math.sin(math.pi * u)))
            points.append((right, eye.cy + eye.ry + 4 + dy))
            pygame.draw.polygon(surface, erase, points)
        elif eye.arc < -0.02:
            # Worried eyes: a heavy upper lid. The sad slant comes from the
            # brows, which is where people actually read it.
            drop = eye.ry * (1.0 - 1.4 * -eye.arc)
            pygame.draw.rect(
                surface, erase,
                pygame.Rect(left, eye.cy - eye.ry - 4 + dy,
                            right - left, (eye.ry - drop) + 4),
            )

        if eye.lid_bottom > 0.5:
            pygame.draw.rect(
                surface, erase,
                pygame.Rect(left, eye.cy + eye.ry - eye.lid_bottom + dy,
                            right - left, eye.lid_bottom + 4),
            )

    def _draw_mouth(self, geo: Layout, dx: float, dy: float) -> None:
        pygame = self.pygame
        col = _rgb(self.cfg.palette.mouth)
        steps = 24
        top, bottom = [], []
        for i in range(steps + 1):
            u = i / steps
            x = geo.mouth_cx - geo.mouth_w / 2 + geo.mouth_w * u + dx
            # A parabola through the corners; the sign of curve flips smile
            # and frown, and mouth_h opens it.
            # Negated: a positive curve has to put the centre of the mouth
            # LOWER than its corners, which is a smile.
            bend = (u - 0.5) ** 2 * 4.0 - 1.0
            y_mid = geo.mouth_cy - bend * geo.mouth_curve * geo.mouth_w * 0.22 + dy
            half = geo.mouth_h / 2 * math.sin(math.pi * u) ** 0.6
            top.append((x, y_mid - half))
            bottom.append((x, y_mid + half))
        pygame.draw.polygon(self.surface, col, top + list(reversed(bottom)))

    def close(self) -> None:
        try:
            self.pygame.quit()
        except Exception:  # pragma: no cover
            pass


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    s = hex_colour.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def make_renderer(preference: str, cfg: FaceConfig) -> FaceRenderer:
    if preference == "sim":
        return HeadlessRenderer()
    try:
        return PygameRenderer(cfg)
    except Exception as exc:
        if preference == "pygame":
            raise
        log.info("No display (%s); face runs headless", exc)
        return HeadlessRenderer()


def random_saccade(strength: float = 1.0) -> tuple[float, float]:
    """A small involuntary eye dart."""
    angle = random.uniform(0, math.tau)
    radius = random.uniform(0.15, 0.5) * strength
    return math.cos(angle) * radius, math.sin(angle) * radius * 0.6
