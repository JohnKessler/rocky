"""The event bus."""

from __future__ import annotations

import asyncio

from rocky.core.bus import EventBus


async def test_exact_topic_delivery(bus: EventBus):
    seen = []
    bus.subscribe("a.b", lambda t, p: _append(seen, t, p))
    bus.publish("a.b", 1)
    bus.publish("a.c", 2)
    await bus.drain()
    assert seen == [("a.b", 1)]


async def test_wildcard_delivery(bus: EventBus):
    seen = []
    bus.subscribe("motion.*", lambda t, p: _append(seen, t, p))
    bus.publish("motion.pose", 1)
    bus.publish("motion.gesture", 2)
    bus.publish("face.expression", 3)
    await bus.drain()
    assert [t for t, _ in seen] == ["motion.pose", "motion.gesture"]


async def test_a_failing_subscriber_cannot_stop_the_robot(bus: EventBus):
    """One broken handler must not take the others with it."""
    survivors = []

    async def explodes(topic, payload):
        raise RuntimeError("boom")

    bus.subscribe("*", explodes)
    bus.subscribe("*", lambda t, p: _append(survivors, t, p))
    bus.publish("x", 1)
    await bus.drain()
    assert survivors == [("x", 1)]


async def test_unsubscribe(bus: EventBus):
    seen = []
    sub = bus.subscribe("*", lambda t, p: _append(seen, t, p))
    bus.publish("x", 1)
    await bus.drain()
    sub.cancel()
    bus.publish("x", 2)
    await bus.drain()
    assert len(seen) == 1


async def test_stream_yields_events(bus: EventBus):
    stream = bus.stream("face.*")
    bus.publish("face.expression", "happy")
    assert await asyncio.wait_for(anext(stream), 1) == ("face.expression", "happy")
    stream.close()


async def test_a_stream_catches_events_published_before_it_is_awaited(bus: EventBus):
    """The websocket creates its stream and then sends an opening snapshot;
    anything published in that window must still arrive."""
    stream = bus.stream("x")
    bus.publish("x", "during the gap")
    await asyncio.sleep(0.01)
    assert await asyncio.wait_for(anext(stream), 1) == ("x", "during the gap")
    stream.close()


async def test_a_full_stream_drops_the_oldest(bus: EventBus):
    """Video and telemetry want the newest frame, not a backlog."""
    stream = bus.stream("x", maxsize=2)
    for i in range(5):
        bus.publish("x", i)
    first = await anext(stream)
    stream.close()
    assert first[1] > 0
    assert bus.stats["dropped"] > 0


def test_publishing_without_a_loop_does_not_raise():
    """Config loading and CLI paths publish outside asyncio."""
    bus = EventBus()
    bus.subscribe("*", lambda t, p: None)
    bus.publish("x", 1)
    assert bus.stats["published"] == 1


async def test_history(bus: EventBus):
    for i in range(5):
        bus.publish("motion.pose", i)
    bus.publish("face.expression", "happy")
    assert len(bus.recent("motion.*")) == 5
    assert bus.recent("*", limit=2)[-1][0] == "face.expression"


def _append(sink, topic, payload):
    async def run():
        sink.append((topic, payload))

    return run()
