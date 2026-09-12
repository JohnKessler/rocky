"""The arithmetic that keeps Rocky inside its own chassis."""

from __future__ import annotations

import math

import pytest
from rocky.motion.kinematics import (
    MECHANICAL_LIMITS,
    AxisState,
    MotionProfile,
    angle_to_pulse_us,
    clamp,
    effective_limits,
    image_offset_to_angles,
    pulse_us_to_duty,
)


class TestLimits:
    def test_config_cannot_exceed_the_chassis(self):
        """A wide-open config must still be clamped to what the print allows."""
        lo, hi = effective_limits("tilt", -90, 90)
        assert (lo, hi) == MECHANICAL_LIMITS["tilt"]

    def test_config_may_be_tighter_than_the_chassis(self):
        assert effective_limits("pan", -30, 30) == (-30, 30)

    def test_reversed_limits_are_reordered(self):
        assert effective_limits("pan", 40, -40) == (-40, 40)

    def test_degenerate_limits_still_leave_travel(self):
        lo, hi = effective_limits("tilt", 5, 5)
        assert hi > lo

    def test_unknown_axis_falls_back_to_a_safe_envelope(self):
        lo, hi = effective_limits("roll", -400, 400)
        assert lo >= -180 and hi <= 180


class TestPulses:
    def test_zero_degrees_is_mid_pulse(self):
        assert angle_to_pulse_us(0, pulse_min_us=500, pulse_max_us=2500, range_deg=180) == 1500

    @pytest.mark.parametrize("angle,expected", [(90, 2500), (-90, 500), (45, 2000)])
    def test_angle_maps_linearly(self, angle, expected):
        got = angle_to_pulse_us(angle, pulse_min_us=500, pulse_max_us=2500, range_deg=180)
        assert got == pytest.approx(expected)

    def test_pulse_is_clamped_to_the_servo_range(self):
        """Even a bad angle must never command a pulse the servo cannot take."""
        for angle in (1000, -1000):
            us = angle_to_pulse_us(angle, pulse_min_us=500, pulse_max_us=2500, range_deg=180)
            assert 500 <= us <= 2500

    def test_invert_mirrors(self):
        kwargs = {"pulse_min_us": 500, "pulse_max_us": 2500, "range_deg": 180}
        assert angle_to_pulse_us(30, invert=True, **kwargs) == angle_to_pulse_us(-30, **kwargs)

    def test_trim_shifts_the_centre(self):
        kwargs = {"pulse_min_us": 500, "pulse_max_us": 2500, "range_deg": 180}
        assert angle_to_pulse_us(0, trim_deg=10, **kwargs) == angle_to_pulse_us(10, **kwargs)

    def test_duty_cycle_is_in_range(self):
        for us in (500, 1500, 2500):
            duty = pulse_us_to_duty(us, 50)
            assert 0 <= duty <= 0xFFFF
        # 1.5ms of a 20ms period is 7.5% of full scale
        assert pulse_us_to_duty(1500, 50) == pytest.approx(0xFFFF * 0.075, rel=0.01)


class TestMotionProfile:
    def _run(self, target, max_speed=150.0, max_accel=600.0, dt=1 / 60):
        profile = MotionProfile(max_speed, max_accel)
        state = AxisState(target=target)
        trace = []
        for _ in range(2000):
            profile.step(state, dt)
            trace.append((state.position, state.velocity))
            if state.at_rest:
                break
        return state, trace

    def test_reaches_the_target(self):
        state, _ = self._run(60.0)
        assert state.position == pytest.approx(60.0, abs=0.05)

    def test_never_overshoots(self):
        """Overshoot on a head this size reads as a twitch, so it is a bug."""
        _, trace = self._run(60.0)
        assert max(p for p, _ in trace) <= 60.0 + 1e-6

    def test_respects_the_speed_ceiling(self):
        _, trace = self._run(120.0, max_speed=90.0)
        assert max(abs(v) for _, v in trace) <= 90.0 + 1e-6

    def test_respects_the_acceleration_ceiling(self):
        """Asserted on the commanded position, which is the physical claim.

        The servo is driven by position, so what has to be bounded is how fast
        the commanded position can change its rate - not the profile's own
        internal velocity variable.
        """
        dt = 1 / 60
        accel = 300.0
        _, trace = self._run(120.0, max_accel=accel, dt=dt)
        positions = [p for p, _ in trace]
        deltas = [b - a for a, b in zip(positions, positions[1:], strict=False)]
        second = [abs(b - a) for a, b in zip(deltas, deltas[1:], strict=False)]
        budget = accel * dt * dt
        assert max(second) <= budget * 1.02

    def test_moves_in_both_directions(self):
        state, _ = self._run(-45.0)
        assert state.position == pytest.approx(-45.0, abs=0.05)

    def test_a_zero_move_settles_immediately(self):
        state, trace = self._run(0.0)
        assert state.at_rest and len(trace) <= 2

    def test_zero_timestep_is_a_no_op(self):
        profile = MotionProfile(150, 600)
        state = AxisState(target=30.0)
        profile.step(state, 0.0)
        assert state.position == 0.0


class TestImageMapping:
    def test_centre_needs_no_movement(self):
        assert image_offset_to_angles(0, 0, h_fov_deg=102, v_fov_deg=67) == (0, 0)

    def test_right_of_centre_pans_right(self):
        pan, _ = image_offset_to_angles(0.25, 0, h_fov_deg=102, v_fov_deg=67)
        assert pan == pytest.approx(25.5)

    def test_below_centre_tilts_down(self):
        """Image y grows downward, so a face low in frame means look down."""
        _, tilt = image_offset_to_angles(0, 0.25, h_fov_deg=102, v_fov_deg=67)
        assert tilt < 0


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10
    assert not math.isnan(clamp(0.0, 0, 1))
