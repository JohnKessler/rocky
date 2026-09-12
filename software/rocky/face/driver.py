"""The face service: animation loop and expression state."""

from __future__ import annotations

import math
import random
import time
from typing import Any

from rocky.core import events as ev
from rocky.core.service import Service
from rocky.face.expressions import EXPRESSION_NAMES, FaceParams, resolve
from rocky.face.renderer import FaceRenderer, make_renderer, random_saccade


class FaceService(Service):
    """Keeps Rocky's face alive.

    Three things are layered on top of each other every frame:

    1. the expression, cross-fading toward whatever was last requested
    2. involuntary life - blinks, saccades, a breathing drift in the glow
    3. gaze, so the pupils lead the head when Rocky turns to look at you

    Layer 2 is what stops the face reading as a picture. A face that holds
    perfectly still is unsettling in a way that is hard to name and impossible
    to miss.
    """

    name = "face"

    def __init__(self, bus, config) -> None:
        super().__init__(bus, config)
        self.renderer: FaceRenderer | None = None

        resting = config.face.resting_expression
        self.current: FaceParams = resolve(resting)
        self._from: FaceParams = self.current
        self._target: FaceParams = self.current
        self._blend_t = 1.0
        self._expression_name = resting
        self._expression_set_at = time.time()
        self._hold_until = 0.0

        self._blink_at = time.time() + 2.0
        self._blink_started = 0.0
        self._saccade_at = time.time() + 1.0
        self._gaze = (0.0, 0.0)
        self._gaze_target = (0.0, 0.0)
        self._speaking = False
        self._speaking_since = 0.0
        self._last_preview = 0.0
        self._fps = 0.0
        # What was actually painted, after blinks, gaze and speech are layered
        # on. snapshot() and the dashboard both read this, so the dashboard
        # mirrors the real face rather than the base expression.
        self.rendered: FaceParams = self.current

    # -- lifecycle ----------------------------------------------------------

    async def setup(self) -> None:
        self.renderer = make_renderer(self.config.hardware.display, self.config.face)
        self.log.info("face renderer: %s", self.renderer.kind)
        self.bus.subscribe(ev.EXPRESSION, self._on_expression)
        self.bus.subscribe(ev.SPEAKING, self._on_speaking)
        self.bus.subscribe(ev.LISTENING, self._on_listening)
        self.bus.subscribe(ev.FACES, self._on_faces)
        self.bus.subscribe(ev.POSE, self._on_pose)

    async def teardown(self) -> None:
        if self.renderer:
            self.renderer.close()
            self.renderer = None

    # -- subscriptions ------------------------------------------------------

    async def _on_expression(self, _topic: str, e: ev.Expression) -> None:
        self.set_expression(e.name, e.intensity, e.hold)

    async def _on_speaking(self, _topic: str, e: ev.Speaking) -> None:
        self._speaking = e.active
        if e.active:
            self._speaking_since = time.time()
        elif self._expression_name in ("speaking", "listening"):
            self.set_expression(self.config.face.resting_expression, 1.0)

    async def _on_listening(self, _topic: str, e: ev.Listening) -> None:
        if e.active:
            self.set_expression("listening", 0.9)
        elif self._expression_name == "listening":
            self.set_expression(self.config.face.resting_expression, 1.0)

    async def _on_faces(self, _topic: str, e: ev.Faces) -> None:
        """Look at whoever is there.

        The eyes lead: they reach the person before the head finishes turning,
        which is how people move and reads as attention rather than as a camera
        slewing.
        """
        target = e.primary
        if target is None:
            return
        track = self.config.face.pupil_track
        self._gaze_target = (
            max(-1.0, min(1.0, (target.cx - 0.5) * 2.4 * track)),
            max(-1.0, min(1.0, (target.cy - 0.5) * 2.0 * track)),
        )
        self._saccade_at = time.time() + 1.6

    async def _on_pose(self, _topic: str, e: ev.Pose) -> None:
        # While the head is still swinging, let the eyes sit slightly ahead of
        # it in the direction of travel.
        if e.moving:
            lead = max(-1.0, min(1.0, (e.target_pan - e.pan) / 25.0)) * 0.4
            gx, gy = self._gaze_target
            self._gaze_target = (max(-1.0, min(1.0, gx + lead)), gy)

    # -- public API ---------------------------------------------------------

    def set_expression(self, name: str, intensity: float = 1.0, hold: float = 0.0) -> bool:
        if name not in EXPRESSION_NAMES:
            self.log.warning("unknown expression: %s", name)
            return False
        self._from = self.current
        self._target = resolve(name, intensity)
        self._blend_t = 0.0
        self._expression_name = name
        self._expression_set_at = time.time()
        self._hold_until = time.time() + hold if hold > 0 else 0.0
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "expression": self._expression_name,
            "renderer": self.renderer.kind if self.renderer else "none",
            "fps": round(self._fps, 1),
            "speaking": self._speaking,
            "params": self.rendered.to_dict(),
        }

    # -- animation ----------------------------------------------------------

    async def run(self) -> None:
        cfg = self.config.face
        period = 1.0 / max(1, cfg.fps)
        last = time.perf_counter()
        while True:
            now = time.perf_counter()
            dt = min(0.25, now - last)
            last = now
            if dt > 0:
                self._fps = self._fps * 0.9 + (1.0 / dt) * 0.1
            try:
                self._animate(dt)
            except KeyboardInterrupt:
                self.log.info("display closed")
                return
            except Exception:
                self.log.exception("face frame failed")
            if not await self.sleep(period):
                return

    def _animate(self, dt: float) -> None:
        cfg = self.config.face
        traits = self.config.identity.traits
        wall = time.time()

        # 1. expression cross-fade
        if self._blend_t < 1.0:
            self._blend_t = min(1.0, self._blend_t + dt / max(0.01, cfg.expression_blend_s))
            self.current = self._from.blend(self._target, _ease(self._blend_t))
        else:
            self.current = self._target

        # drift back to resting once an expression has had its moment
        if self._hold_until and wall > self._hold_until:
            self._hold_until = 0.0
            self.set_expression(cfg.resting_expression)
        elif (
            not self._hold_until
            and self._expression_name != cfg.resting_expression
            and not self._speaking
            and wall - self._expression_set_at > cfg.idle_decay_s
        ):
            self.set_expression(cfg.resting_expression)

        params = self.current

        # 2. involuntary life
        params = self._apply_blink(params, wall, traits.energy)
        params = self._apply_gaze(params, dt, wall, traits)
        params = self._apply_breath(params, wall)

        # 3. mouth movement while speaking
        if self._speaking:
            params = self._apply_speech(params, wall)

        self.rendered = params
        if self.renderer:
            self.renderer.draw(params, wall)

        if wall - self._last_preview >= 1.0 / max(1, cfg.preview_fps):
            self._last_preview = wall
            self.bus.publish(
                ev.FACE_FRAME,
                {"expression": self._expression_name, "params": params.to_dict()},
            )

    def _apply_blink(self, p: FaceParams, wall: float, energy: float) -> FaceParams:
        cfg = self.config.face
        if self._blink_started:
            phase = (wall - self._blink_started) / max(0.02, cfg.blink_duration_s)
            if phase >= 1.0:
                self._blink_started = 0.0
                self._schedule_blink(wall, energy)
            else:
                # Down fast, up a little slower - the shape of a real blink.
                closed = math.sin(phase * math.pi) ** 0.7
                factor = max(0.0, 1.0 - closed)
                return p.with_(
                    eye_open_l=p.eye_open_l * factor,
                    eye_open_r=p.eye_open_r * factor,
                )
        elif wall >= self._blink_at:
            self._blink_started = wall
        return p

    def _schedule_blink(self, wall: float, energy: float) -> None:
        cfg = self.config.face
        # Livelier Rocky blinks more often.
        scale = 1.35 - 0.7 * energy
        lo = cfg.blink_min_s * scale
        hi = max(lo + 0.2, cfg.blink_max_s * scale)
        self._blink_at = wall + random.uniform(lo, hi)

    def _apply_gaze(self, p: FaceParams, dt: float, wall: float, traits: Any) -> FaceParams:
        cfg = self.config.face
        if cfg.saccade_rate > 0 and wall >= self._saccade_at:
            # Less focused Rocky lets its eyes wander more.
            interval = 1.0 / cfg.saccade_rate * (0.5 + traits.focus)
            self._saccade_at = wall + random.uniform(interval * 0.5, interval * 1.8)
            self._gaze_target = random_saccade(0.8 * (1.3 - traits.focus))

        gx, gy = self._gaze
        tx, ty = self._gaze_target
        k = min(1.0, dt * 9.0)
        self._gaze = (gx + (tx - gx) * k, gy + (ty - gy) * k)
        return p.with_(
            pupil_x=max(-1.0, min(1.0, p.pupil_x + self._gaze[0])),
            pupil_y=max(-1.0, min(1.0, p.pupil_y + self._gaze[1])),
        )

    def _apply_breath(self, p: FaceParams, wall: float) -> FaceParams:
        """A slow swell in the glow. Subliminal, but the face feels warm
        rather than switched-on."""
        swell = (math.sin(wall * 0.6) + 1.0) * 0.5
        return p.with_(glow=max(0.0, min(1.0, p.glow * (0.88 + 0.12 * swell))))

    def _apply_speech(self, p: FaceParams, wall: float) -> FaceParams:
        """Mouth movement synchronised to nothing in particular.

        Rocky does not have phonemes - it speaks in chords - so a plausible
        rhythm beats a bad lip sync. Two detuned oscillators give a mouth that
        never repeats an obvious pattern.
        """
        t = wall - self._speaking_since
        a = math.sin(t * 11.0) * 0.5 + 0.5
        b = math.sin(t * 6.3 + 1.1) * 0.5 + 0.5
        openness = 0.16 + 0.62 * (a * 0.65 + b * 0.35) ** 1.4
        return p.with_(
            mouth_open=max(p.mouth_open, openness),
            mouth_width=p.mouth_width * (0.94 + 0.1 * b),
        )


def _ease(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)
