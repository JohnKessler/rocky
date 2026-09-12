"""Angles, pulses and motion profiles.

Nothing here talks to hardware. It is pure arithmetic, which is what lets the
tests check that Rocky cannot drive itself into its own end stops.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The envelope the printed parts physically allow, from hardware/cad.
# Software limits in config.toml are clamped into this; the printed stop post
# in the base and the stop pins on the yoke are the layer behind that.
MECHANICAL_LIMITS: dict[str, tuple[float, float]] = {
    "pan": (-100.0, 100.0),
    "tilt": (-26.0, 26.0),
}


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def effective_limits(axis: str, cfg_min: float, cfg_max: float) -> tuple[float, float]:
    """Intersect the configured limits with what the chassis allows.

    Called on every command, not just at startup, so editing a limit in the
    dashboard can loosen travel up to the mechanical envelope and no further.
    """
    hard_lo, hard_hi = MECHANICAL_LIMITS.get(axis, (-180.0, 180.0))
    lo = clamp(min(cfg_min, cfg_max), hard_lo, hard_hi)
    hi = clamp(max(cfg_min, cfg_max), hard_lo, hard_hi)
    if hi - lo < 1.0:  # degenerate config; give the axis a usable sliver
        mid = clamp((lo + hi) / 2, hard_lo, hard_hi)
        lo, hi = max(hard_lo, mid - 0.5), min(hard_hi, mid + 0.5)
    return lo, hi


def angle_to_pulse_us(
    angle_deg: float,
    *,
    pulse_min_us: int,
    pulse_max_us: int,
    range_deg: float,
    trim_deg: float = 0.0,
    invert: bool = False,
) -> float:
    """Map an angle in Rocky's frame onto a servo pulse width.

    Angle 0 is straight ahead and sits at the midpoint of the pulse range;
    ``trim_deg`` moves that midpoint to wherever the horn actually splined on.
    """
    a = -angle_deg if invert else angle_deg
    a += trim_deg
    span = pulse_max_us - pulse_min_us
    mid = pulse_min_us + span / 2.0
    us = mid + (a / range_deg) * span
    return clamp(us, float(pulse_min_us), float(pulse_max_us))


def pulse_us_to_duty(pulse_us: float, frequency_hz: int, *, bits: int = 16) -> int:
    """Convert a pulse width to a PCA9685 duty value."""
    period_us = 1_000_000.0 / frequency_hz
    duty = (pulse_us / period_us) * ((1 << bits) - 1)
    return int(clamp(round(duty), 0, (1 << bits) - 1))


@dataclass
class AxisState:
    """Where an axis is and how fast it is going."""

    position: float = 0.0
    velocity: float = 0.0
    target: float = 0.0

    @property
    def at_rest(self) -> bool:
        return abs(self.velocity) < 0.05 and abs(self.target - self.position) < 0.1


class MotionProfile:
    """Velocity-limited, acceleration-limited approach to a target.

    Rocky's head should arrive and stop, not overshoot and hunt, so the profile
    computes the fastest speed from which it can still brake to a standstill
    exactly on target and never exceeds it. The result is a trapezoid: ramp up,
    cruise, ramp down - the movement people read as deliberate rather than
    servo-ish.
    """

    def __init__(self, max_speed: float, max_accel: float) -> None:
        self.max_speed = max(1e-3, max_speed)
        self.max_accel = max(1e-3, max_accel)

    def step(self, state: AxisState, dt: float) -> AxisState:
        if dt <= 0:
            return state

        error = state.target - state.position

        # Fastest speed we can be doing now and still stop exactly on target.
        # This is the DISCRETE-time solution, not v = sqrt(2*a*d): the step
        # advances position at the start-of-step velocity, so the continuous
        # form permits a speed that overshoots by up to one step. Solving
        # v^2 + 2*a*dt*v - 2*a*d <= 0 accounts for that step.
        a_dt = self.max_accel * dt
        stopping_speed = -a_dt + math.sqrt(a_dt * a_dt + 2.0 * self.max_accel * abs(error))
        desired = math.copysign(min(self.max_speed, max(0.0, stopping_speed)), error)

        # Respect the acceleration ceiling on the way to that speed.
        dv_limit = self.max_accel * dt
        dv = clamp(desired - state.velocity, -dv_limit, dv_limit)
        velocity = state.velocity + dv

        position = state.position + velocity * dt

        # Settle onto the target once we are already essentially stopped.
        # The braking curve drives speed to zero as the error does, so the
        # velocity discarded here is negligible. Snapping on remaining
        # distance alone would discard a large velocity in one tick and
        # break the very limit this class exists to enforce.
        if abs(state.target - position) < 0.02 and abs(velocity) < 0.5:
            position, velocity = state.target, 0.0

        state.position = position
        state.velocity = velocity
        return state


def ease_in_out(t: float) -> float:
    """Smoothstep, for keyframed gestures where the profile is not in charge."""
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ease_out_back(t: float, overshoot: float = 1.7) -> float:
    """Overshoot and settle - gives a nod a bit of life."""
    t = clamp(t, 0.0, 1.0) - 1.0
    return t * t * ((overshoot + 1) * t + overshoot) + 1.0


def image_offset_to_angles(
    dx: float,
    dy: float,
    *,
    h_fov_deg: float,
    v_fov_deg: float,
) -> tuple[float, float]:
    """Turn a normalised offset from image centre into a relative pan/tilt.

    ``dx``/``dy`` run -0.5 to +0.5. Positive dx is right of centre; positive dy
    is below centre, so the tilt term is negated - a face low in the frame
    means look down.
    """
    return dx * h_fov_deg, -dy * v_fov_deg
