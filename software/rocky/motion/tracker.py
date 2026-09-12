"""Turning "there is a face at (0.63, 0.41)" into "pan right by 13 degrees"."""

from __future__ import annotations

import time
from dataclasses import dataclass

from rocky.config import TrackingConfig, VisionConfig
from rocky.core.events import Faces
from rocky.motion.kinematics import image_offset_to_angles


@dataclass
class TrackResult:
    """What the tracker wants the head to do this frame."""

    pan_delta: float
    tilt_delta: float
    locked: bool
    target_area: float = 0.0


class FaceTracker:
    """Proportional tracker with a deadband and a memory.

    Deliberately not a full PID. Integral term on a servo with backlash walks
    the head slowly off target; derivative term on a jittery detector makes it
    twitch. Proportional plus a deadband plus the motion profile's own
    acceleration limit produces the unhurried "turning to look at you" that
    reads as attention rather than machinery.
    """

    def __init__(self, cfg: TrackingConfig, vision: VisionConfig) -> None:
        self.cfg = cfg
        self.vision = vision
        self._last_seen = 0.0
        self._last_delta = (0.0, 0.0)

    def update(self, faces: Faces | None, now: float | None = None) -> TrackResult:
        now = now if now is not None else time.time()
        target = faces.primary if faces else None

        if target is None:
            # Keep the last correction briefly so a one-frame detector dropout
            # does not make the head stop dead mid-turn.
            if now - self._last_seen < self.cfg.lost_target_hold_s:
                pan, tilt = self._last_delta
                return TrackResult(pan * 0.5, tilt * 0.5, locked=True)
            self._last_delta = (0.0, 0.0)
            return TrackResult(0.0, 0.0, locked=False)

        self._last_seen = now

        dx = target.cx - 0.5
        dy = (target.cy - 0.5) + self.cfg.vertical_bias

        # Inside the deadband Rocky holds still. Without this the head creeps
        # continuously, chasing sub-pixel detector noise.
        if abs(dx) < self.cfg.deadband:
            dx = 0.0
        if abs(dy) < self.cfg.deadband:
            dy = 0.0

        pan_err, tilt_err = image_offset_to_angles(
            dx, dy, h_fov_deg=self.vision.h_fov_deg, v_fov_deg=self.vision.v_fov_deg
        )

        pan = pan_err * self.cfg.gain
        tilt = tilt_err * self.cfg.gain

        # Light first-order damping between frames smooths detector jitter
        # without adding the phase lag a derivative term would.
        d = self.cfg.damping
        pan = pan * (1 - d) + self._last_delta[0] * d
        tilt = tilt * (1 - d) + self._last_delta[1] * d
        self._last_delta = (pan, tilt)

        return TrackResult(pan, tilt, locked=True, target_area=target.area)

    @property
    def has_target(self) -> bool:
        return time.time() - self._last_seen < self.cfg.lost_target_hold_s
