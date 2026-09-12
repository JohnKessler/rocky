"""The brain's tools.

Tools act by publishing bus events, so these tests assert on what reached the
bus - the same path the dashboard's buttons take.
"""

from __future__ import annotations

import pytest
from rocky.brain import tools
from rocky.brain.memory import Memory
from rocky.core import events as ev
from rocky.vision.camera import SimCamera


class Context:
    """A minimal ToolContext."""

    def __init__(self, config, bus, memory, camera=None):
        self.config = config
        self.bus = bus
        self.memory = memory
        self._camera = camera

    def latest_frame(self):
        return self._camera.capture() if self._camera else None

    def status(self):
        return {"uptime_s": 12.0, "cpu_temp_c": 48.1}


@pytest.fixture
def ctx(config, bus, tmp_path):
    return Context(config, bus, Memory(str(tmp_path / "m.db")), SimCamera(config.vision))


async def test_schemas_are_well_formed():
    for schema in tools.TOOL_SCHEMAS:
        assert schema["name"] and schema["description"]
        assert schema["input_schema"]["type"] == "object"
    assert set(tools.TOOL_NAMES) == set(tools.HANDLERS)


async def test_set_expression_publishes(ctx, collected, bus):
    result, error = tools.execute(ctx, "set_expression", {"expression": "happy", "intensity": 0.6})
    await bus.drain()
    assert not error
    published = [p for t, p in collected if t == ev.EXPRESSION]
    assert published[0].name == "happy" and published[0].intensity == 0.6


async def test_unknown_expression_is_reported_not_published(ctx, collected, bus):
    result, error = tools.execute(ctx, "set_expression", {"expression": "smug"})
    await bus.drain()
    assert "smug" in result
    assert not [p for t, p in collected if t == ev.EXPRESSION]


async def test_move_publishes_a_gesture(ctx, collected, bus):
    tools.execute(ctx, "move", {"gesture": "nod", "intensity": 0.8})
    await bus.drain()
    assert [p for t, p in collected if t == ev.GESTURE][0].name == "nod"


async def test_look_at_person_switches_to_tracking(ctx, collected, bus):
    tools.execute(ctx, "look", {"target": "person"})
    await bus.drain()
    assert ("motion.mode", "track") in [(t, p) for t, p in collected]


async def test_look_in_a_direction_commands_an_angle(ctx, collected, bus):
    tools.execute(ctx, "look", {"target": "left", "amount": 0.5})
    await bus.drain()
    look = [p for t, p in collected if t == ev.LOOK_AT][0]
    assert look.frame == "world" and look.x < 0


async def test_see_returns_the_actual_image(ctx):
    """The model has to look at the picture, not read a description of it."""
    result, error = tools.execute(ctx, "see", {})
    assert not error
    assert [b["type"] for b in result] == ["image", "text"]
    assert result[0]["source"]["type"] == "base64"
    assert result[0]["source"]["media_type"] == "image/png"
    assert len(result[0]["source"]["data"]) > 100


async def test_see_without_a_camera_says_so(config, bus, tmp_path):
    ctx = Context(config, bus, Memory(str(tmp_path / "m.db")), camera=None)
    result, error = tools.execute(ctx, "see", {})
    assert isinstance(result, str) and not error


async def test_remember_and_recall(ctx):
    tools.execute(ctx, "remember", {"fact": "John flies gliders", "category": "people"})
    result, _ = tools.execute(ctx, "recall", {"query": "gliders"})
    assert "gliders" in result


async def test_recall_with_nothing_stored(ctx):
    result, error = tools.execute(ctx, "recall", {"query": "anything"})
    assert not error and "do not have" in result


async def test_adjust_self_changes_a_trait(ctx, collected, bus):
    """Rocky can retune itself when asked to be different."""
    result, error = tools.execute(ctx, "adjust_self", {"trait": "chattiness", "value": 0.15})
    await bus.drain()
    assert not error
    assert ctx.config.identity.traits.chattiness == pytest.approx(0.15)
    assert [p for t, p in collected if t == ev.CONFIG_CHANGED]


async def test_adjust_self_respects_bounds(ctx):
    result, error = tools.execute(ctx, "adjust_self", {"trait": "energy", "value": 5.0})
    assert "cannot change" in result
    assert ctx.config.identity.traits.energy <= 1.0


async def test_an_unknown_tool_is_an_error_not_an_exception(ctx):
    result, error = tools.execute(ctx, "self_destruct", {})
    assert error and "self_destruct" in result


async def test_a_throwing_handler_is_contained(ctx, monkeypatch):
    """A broken tool must not take the conversation down with it."""
    def explode(context, args):
        raise RuntimeError("nope")

    monkeypatch.setitem(tools.HANDLERS, "move", explode)
    result, error = tools.execute(ctx, "move", {"gesture": "nod"})
    assert error and "nope" in result
