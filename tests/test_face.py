"""Expressions and the geometry both renderers share."""

from __future__ import annotations

import math

import pytest
from rocky.config import FaceConfig
from rocky.face.expressions import EXPRESSION_NAMES, EXPRESSIONS, FaceParams, resolve
from rocky.face.renderer import HeadlessRenderer, layout, make_renderer


class TestExpressions:
    def test_every_name_resolves(self):
        for name in EXPRESSION_NAMES:
            assert isinstance(resolve(name), FaceParams)

    def test_an_unknown_name_falls_back_rather_than_raising(self):
        assert resolve("smug") == EXPRESSIONS["neutral"]

    def test_intensity_interpolates_toward_neutral(self):
        full, half = resolve("happy"), resolve("happy", 0.5)
        assert half.mouth_curve == pytest.approx(
            (EXPRESSIONS["neutral"].mouth_curve + full.mouth_curve) / 2
        )

    def test_zero_intensity_is_neutral(self):
        assert resolve("happy", 0.0) == EXPRESSIONS["neutral"]

    def test_blend_endpoints(self):
        a, b = EXPRESSIONS["sad"], EXPRESSIONS["happy"]
        assert a.blend(b, 0.0) == a
        assert a.blend(b, 1.0) == b

    def test_blend_is_clamped(self):
        a, b = EXPRESSIONS["sad"], EXPRESSIONS["happy"]
        assert a.blend(b, 5.0) == b
        assert a.blend(b, -5.0) == a

    def test_expressions_are_distinguishable(self):
        """Two emotions that render identically are one emotion with two
        names, which would make the brain's choice meaningless."""
        seen: dict[tuple, str] = {}
        for name in EXPRESSION_NAMES:
            key = tuple(resolve(name).to_dict().values())
            assert key not in seen, f"{name} is identical to {seen.get(key)}"
            seen[key] = name

    def test_emotional_direction_is_right(self):
        assert EXPRESSIONS["happy"].mouth_curve > 0
        assert EXPRESSIONS["sad"].mouth_curve < 0
        assert EXPRESSIONS["surprised"].eye_open_l > EXPRESSIONS["neutral"].eye_open_l
        assert EXPRESSIONS["sleepy"].eye_open_l < EXPRESSIONS["neutral"].eye_open_l


class TestGeometry:
    cfg = FaceConfig(width=720, height=720)

    def test_eyes_are_symmetric_about_the_centre(self):
        g = layout(resolve("neutral"), self.cfg)
        assert g.left.cx + g.right.cx == pytest.approx(self.cfg.width)

    @pytest.mark.parametrize("name", list(EXPRESSION_NAMES))
    def test_the_pupil_never_leaves_the_eye(self, name):
        """A pupil that slides outside its eye is the single most obviously
        broken thing a face can do."""
        g = layout(resolve(name), self.cfg)
        for eye in (g.left, g.right):
            if eye.ry < 1:
                continue
            # An eye narrower than its own pupil (a hard squint) has no
            # travel at all, so the bound floors at zero rather than going
            # negative.
            dx = abs(eye.pupil_cx - eye.cx)
            dy = abs(eye.pupil_cy - eye.cy)
            assert dx <= max(0.0, eye.rx - eye.pupil_r) + 0.01
            assert dy <= max(0.0, eye.ry - eye.pupil_r) + 0.01

    @pytest.mark.parametrize("name", list(EXPRESSION_NAMES))
    def test_nothing_is_drawn_off_screen(self, name):
        g = layout(resolve(name), self.cfg)
        for eye in (g.left, g.right):
            assert 0 <= eye.cx - eye.rx and eye.cx + eye.rx <= self.cfg.width
        assert g.mouth_cx - g.mouth_w / 2 >= 0
        assert g.mouth_cy + g.mouth_h <= self.cfg.height

    def test_a_smile_puts_the_mouth_centre_below_its_corners(self):
        """Positive curve means smile. The sign was inverted once; it drew
        every happy face as a frown."""
        g = layout(resolve("happy"), self.cfg)
        corner = self._mouth_y(g, 0.0)
        centre = self._mouth_y(g, 0.5)
        assert centre > corner

    def test_a_frown_puts_the_mouth_centre_above_its_corners(self):
        g = layout(resolve("sad"), self.cfg)
        assert self._mouth_y(g, 0.5) < self._mouth_y(g, 0.0)

    @staticmethod
    def _mouth_y(g, u: float) -> float:
        bend = (u - 0.5) ** 2 * 4.0 - 1.0
        return g.mouth_cy - bend * g.mouth_curve * g.mouth_w * 0.22

    def test_a_bigger_arc_hides_more_of_the_eye(self):
        """The eyelid must scale with arc. It once covered the whole lower
        half regardless, which erased the pupils of every smiling face."""
        def hidden(name: str) -> float:
            e = layout(resolve(name), self.cfg).left
            base = e.cy + e.ry * (1.0 - 1.55 * e.arc)
            return (e.cy + e.ry - base) / (2 * e.ry)

        assert hidden("content") < hidden("happy") < hidden("delighted")
        assert hidden("delighted") < 0.95, "a delighted Rocky must keep some eye"

    def test_shake_only_jitters_when_asked(self):
        assert layout(resolve("neutral"), self.cfg, t=1.0).jitter == (0.0, 0.0)
        jitter = layout(resolve("alarm"), self.cfg, t=1.0).jitter
        assert math.hypot(*jitter) > 0

    def test_geometry_scales_with_the_panel(self):
        small = layout(resolve("neutral"), FaceConfig(width=240, height=240))
        big = layout(resolve("neutral"), FaceConfig(width=720, height=720))
        assert big.left.rx == pytest.approx(small.left.rx * 3)


def test_headless_renderer_is_chosen_without_a_display():
    renderer = make_renderer("auto", FaceConfig())
    assert isinstance(renderer, HeadlessRenderer)
    renderer.draw(resolve("happy"), 0.0)
    assert renderer.frames == 1
