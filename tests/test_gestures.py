"""Body language."""

from __future__ import annotations

import pytest
from rocky.motion.gestures import GESTURE_NAMES, GESTURES, get


class TestGestures:
    @pytest.mark.parametrize("name", list(GESTURE_NAMES))
    def test_starts_and_ends_at_rest(self, name):
        """A gesture is an offset layered on top of wherever Rocky is
        pointing, so one that does not return to zero permanently drags the
        head off target."""
        g = GESTURES[name]
        assert g.sample(0.0) == (0.0, 0.0)
        assert g.sample(g.duration) == (0.0, 0.0)

    @pytest.mark.parametrize("name", list(GESTURE_NAMES))
    def test_stays_within_a_sane_amplitude(self, name):
        """Large moves read as a malfunction rather than as body language."""
        g = GESTURES[name]
        for i in range(80):
            pan, tilt = g.sample(g.duration * i / 79)
            assert abs(pan) <= 25 and abs(tilt) <= 15

    @pytest.mark.parametrize("name", list(GESTURE_NAMES))
    def test_is_continuous(self, name):
        g = GESTURES[name]
        steps = 200
        prev = g.sample(0.0)
        for i in range(1, steps + 1):
            cur = g.sample(g.duration * i / steps)
            assert abs(cur[0] - prev[0]) < 6.0
            assert abs(cur[1] - prev[1]) < 6.0
            prev = cur

    def test_sampling_past_the_end_holds(self):
        g = GESTURES["nod"]
        assert g.sample(g.duration * 5) == g.sample(g.duration)

    def test_a_nod_moves_in_tilt_and_a_shake_in_pan(self):
        nod_tilt = max(abs(GESTURES["nod"].sample(t / 20)[1]) for t in range(16))
        nod_pan = max(abs(GESTURES["nod"].sample(t / 20)[0]) for t in range(16))
        assert nod_tilt > nod_pan
        shake_pan = max(abs(GESTURES["shake"].sample(t / 20)[0]) for t in range(16))
        shake_tilt = max(abs(GESTURES["shake"].sample(t / 20)[1]) for t in range(16))
        assert shake_pan > shake_tilt

    def test_unknown_gesture_returns_none(self):
        assert get("moonwalk") is None

    def test_all_have_a_description(self):
        for g in GESTURES.values():
            assert g.description
