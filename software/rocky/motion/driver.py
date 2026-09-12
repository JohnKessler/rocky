"""The motion service: one control loop that owns the servos."""

from __future__ import annotations

import random
import time
from typing import Any

from rocky.core import events as ev
from rocky.core.service import Service
from rocky.motion.gestures import GestureDef
from rocky.motion.gestures import get as get_gesture
from rocky.motion.kinematics import (
    AxisState,
    MotionProfile,
    angle_to_pulse_us,
    clamp,
    effective_limits,
)
from rocky.motion.servo import ServoBackend, make_servo_backend
from rocky.motion.tracker import FaceTracker


class MotionService(Service):
    """Drives pan and tilt.

    Everything that wants to move the head publishes an event; this loop is the
    only thing that writes to a servo. That single-writer rule is what keeps
    tracking, gestures and dashboard jogging from fighting each other.

    The commanded angle each tick is::

        base (tracking, or a look_at, or idle drift) + gesture overlay

    so Rocky can nod while still looking at you.
    """

    name = "motion"

    def __init__(self, bus, config) -> None:
        super().__init__(bus, config)
        self.backend: ServoBackend | None = None
        self.pan = AxisState()
        self.tilt = AxisState()
        self.mode = "track"

        self._tracker = FaceTracker(config.motion.tracking, config.vision)
        self._faces: ev.Faces | None = None
        self._gesture: GestureDef | None = None
        self._gesture_started = 0.0
        self._gesture_intensity = 1.0
        self._energised = False
        self._rest_since = 0.0
        self._last_pose_publish = 0.0
        self._next_scan = time.time() + config.motion.idle.scan_interval_s
        self._next_micro = time.time() + config.motion.idle.micro_move_interval_s
        self._last_command: tuple[float, float] | None = None

    # -- lifecycle ----------------------------------------------------------

    async def setup(self) -> None:
        mc = self.config.motion
        self.backend = make_servo_backend(
            self.config.hardware.servos, mc.i2c_address, mc.pwm_frequency
        )
        self.log.info("servo backend: %s", self.backend.kind)

        self.bus.subscribe(ev.LOOK_AT, self._on_look_at)
        self.bus.subscribe(ev.GESTURE, self._on_gesture)
        self.bus.subscribe(ev.FACES, self._on_faces)
        self.bus.subscribe(ev.MOTION_MODE, self._on_mode)
        self.bus.subscribe(ev.SPEAKING, self._on_speaking)

    async def teardown(self) -> None:
        if self.backend:
            self.backend.close()
            self.backend = None

    # -- subscriptions ------------------------------------------------------

    async def _on_look_at(self, _topic: str, e: ev.LookAt) -> None:
        if self.mode == "off":
            return
        if e.frame == "world":
            self._set_target(e.x, e.y)
        else:
            # Normalised image coords: treat as an offset from where we point.
            from rocky.motion.kinematics import image_offset_to_angles

            dpan, dtilt = image_offset_to_angles(
                e.x - 0.5, e.y - 0.5,
                h_fov_deg=self.config.vision.h_fov_deg,
                v_fov_deg=self.config.vision.v_fov_deg,
            )
            self._set_target(self.pan.target + dpan, self.tilt.target + dtilt)
        # An explicit look overrides tracking until something re-enables it.
        if self.mode == "idle":
            self.mode = "track"

    async def _on_gesture(self, _topic: str, e: ev.Gesture) -> None:
        if self.mode == "off":
            return
        gesture = get_gesture(e.name)
        if gesture is None:
            self.log.warning("unknown gesture: %s", e.name)
            return
        self._gesture = gesture
        self._gesture_started = time.time()
        # Energy scales how big a move reads, so a sleepy Rocky nods smaller.
        self._gesture_intensity = clamp(
            e.intensity * (0.55 + 0.75 * self.config.identity.traits.energy), 0.0, 2.0
        )

    async def _on_faces(self, _topic: str, e: ev.Faces) -> None:
        self._faces = e

    async def _on_mode(self, _topic: str, payload: Any) -> None:
        mode = payload if isinstance(payload, str) else getattr(payload, "mode", None)
        if mode in ("track", "manual", "idle", "off"):
            self.mode = mode
            self.log.info("mode -> %s", mode)
            if mode == "off":
                self._release()

    async def _on_speaking(self, _topic: str, e: ev.Speaking) -> None:
        # A small settle at the end of a sentence stops Rocky freezing the
        # instant the audio does, which looks like a crash.
        if not e.active and self._gesture is None and self.mode != "off":
            await self._on_gesture(ev.GESTURE, ev.Gesture("settle", 0.5))

    # -- control loop -------------------------------------------------------

    async def run(self) -> None:
        period = 1.0 / max(1, self.config.motion.update_hz)
        last = time.perf_counter()
        while True:
            now = time.perf_counter()
            dt = min(0.2, now - last)
            last = now
            try:
                self._tick(dt)
            except Exception:
                self.log.exception("motion tick failed")
            if not await self.sleep(period):
                return

    def _tick(self, dt: float) -> None:
        mc = self.config.motion
        wall = time.time()

        if self.mode == "track" and mc.tracking.enabled:
            result = self._tracker.update(self._faces, wall)
            if result.locked and (result.pan_delta or result.tilt_delta):
                self._set_target(
                    self.pan.target + result.pan_delta * dt * 6.0,
                    self.tilt.target + result.tilt_delta * dt * 6.0,
                )
            elif not result.locked:
                self._idle_behaviour(wall)
        elif self.mode == "idle":
            self._idle_behaviour(wall)

        # Advance both axes along their profiles.
        MotionProfile(mc.pan.max_speed_dps, mc.pan.max_accel_dps2).step(self.pan, dt)
        MotionProfile(mc.tilt.max_speed_dps, mc.tilt.max_accel_dps2).step(self.tilt, dt)

        gp, gt = self._gesture_offsets(wall)
        pan_cmd, tilt_cmd = self._clamped(self.pan.position + gp, self.tilt.position + gt)

        moving = not (self.pan.at_rest and self.tilt.at_rest) or self._gesture is not None
        if moving:
            self._rest_since = wall
            self._write(pan_cmd, tilt_cmd)
        elif self._energised and mc.idle_torque_off_s > 0:
            if wall - self._rest_since >= mc.idle_torque_off_s:
                self._release()
        elif self._energised:
            self._write(pan_cmd, tilt_cmd)

        if wall - self._last_pose_publish >= 0.1:
            self._last_pose_publish = wall
            self.bus.publish(
                ev.POSE,
                ev.Pose(
                    pan=round(pan_cmd, 2),
                    tilt=round(tilt_cmd, 2),
                    target_pan=round(self.pan.target, 2),
                    target_tilt=round(self.tilt.target, 2),
                    moving=moving,
                    torque=self._energised,
                ),
            )

    def _gesture_offsets(self, wall: float) -> tuple[float, float]:
        if self._gesture is None:
            return 0.0, 0.0
        t = wall - self._gesture_started
        if t > self._gesture.duration:
            self._gesture = None
            return 0.0, 0.0
        pan, tilt = self._gesture.sample(t)
        return pan * self._gesture_intensity, tilt * self._gesture_intensity

    def _idle_behaviour(self, wall: float) -> None:
        idle = self.config.motion.idle
        if not idle.enabled:
            return
        curiosity = self.config.identity.traits.curiosity

        if wall >= self._next_scan:
            # Curious Rocky looks around more often and further.
            self._next_scan = wall + idle.scan_interval_s * (1.6 - curiosity)
            amp = idle.scan_amplitude_deg * (0.4 + curiosity)
            self._set_target(random.uniform(-amp, amp), random.uniform(-6.0, 4.0))
            return

        if wall >= self._next_micro:
            self._next_micro = wall + idle.micro_move_interval_s * random.uniform(0.6, 1.6)
            d = idle.micro_move_deg
            self._set_target(
                self.pan.target + random.uniform(-d, d),
                self.tilt.target + random.uniform(-d * 0.6, d * 0.6),
            )

    # -- output -------------------------------------------------------------

    def _clamped(self, pan: float, tilt: float) -> tuple[float, float]:
        mc = self.config.motion
        p_lo, p_hi = effective_limits("pan", mc.pan.min_deg, mc.pan.max_deg)
        t_lo, t_hi = effective_limits("tilt", mc.tilt.min_deg, mc.tilt.max_deg)
        return clamp(pan, p_lo, p_hi), clamp(tilt, t_lo, t_hi)

    def _set_target(self, pan: float, tilt: float) -> None:
        self.pan.target, self.tilt.target = self._clamped(pan, tilt)

    def _write(self, pan: float, tilt: float) -> None:
        if self.backend is None or not self.config.motion.enabled:
            return
        command = (round(pan, 2), round(tilt, 2))
        if command == self._last_command and self._energised:
            return  # nothing changed; do not spam the I2C bus
        self._last_command = command
        for axis_cfg, angle in ((self.config.motion.pan, pan), (self.config.motion.tilt, tilt)):
            self.backend.set_pulse(
                axis_cfg.channel,
                angle_to_pulse_us(
                    angle,
                    pulse_min_us=axis_cfg.pulse_min_us,
                    pulse_max_us=axis_cfg.pulse_max_us,
                    range_deg=axis_cfg.range_deg,
                    trim_deg=axis_cfg.centre_trim_deg,
                    invert=axis_cfg.invert,
                ),
            )
        self._energised = True

    def _release(self) -> None:
        if self.backend is None:
            return
        self.backend.release(self.config.motion.pan.channel)
        self.backend.release(self.config.motion.tilt.channel)
        self._energised = False
        self._last_command = None

    # -- used by the dashboard ---------------------------------------------

    def jog(self, pan: float | None = None, tilt: float | None = None) -> tuple[float, float]:
        """Absolute move, for the dashboard's jog controls."""
        self.mode = "manual"
        self._set_target(
            self.pan.target if pan is None else pan,
            self.tilt.target if tilt is None else tilt,
        )
        return self.pan.target, self.tilt.target

    def snapshot(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "pan": round(self.pan.position, 2),
            "tilt": round(self.tilt.position, 2),
            "target_pan": round(self.pan.target, 2),
            "target_tilt": round(self.tilt.target, 2),
            "torque": self._energised,
            "gesture": self._gesture.name if self._gesture else None,
            "tracking": self._tracker.has_target,
            "backend": self.backend.kind if self.backend else "none",
        }
