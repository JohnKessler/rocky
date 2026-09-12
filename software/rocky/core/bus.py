"""A small asyncio publish/subscribe bus.

Services never import each other. They publish events and subscribe to topics,
which keeps the wiring in one place (``rocky.app``) and makes every service
testable by feeding it events directly.

Two delivery styles:

``subscribe``   an async callback, invoked in a task per event. Use for
                anything that reacts - the face, the servos.
``stream``      an async iterator with a bounded queue. Use when you need
                back-pressure or ordering, like the websocket feed.

A slow or failing subscriber must never wedge the robot, so callbacks run
detached and exceptions are logged, not propagated.
"""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

Handler = Callable[[str, Any], Awaitable[None]]


class Subscription:
    """Handle returned by :meth:`EventBus.subscribe`; cancel to unsubscribe."""

    def __init__(self, bus: EventBus, pattern: str, handler: Handler) -> None:
        self._bus = bus
        self._pattern = pattern
        self._handler = handler

    def cancel(self) -> None:
        self._bus._remove(self._pattern, self._handler)

    def __enter__(self) -> Subscription:
        return self

    def __exit__(self, *exc: object) -> None:
        self.cancel()


class EventBus:
    """In-process pub/sub with glob topic matching."""

    def __init__(self, *, history: int = 200) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._queues: list[tuple[str, asyncio.Queue]] = []
        self._tasks: set[asyncio.Task] = set()
        self._history_limit = history
        self._history: list[tuple[str, Any]] = []
        self._published = 0
        self._dropped = 0

    # -- publishing ---------------------------------------------------------

    def publish(self, topic: str, payload: Any = None) -> None:
        """Fire an event. Never blocks and never raises.

        Deliberately synchronous: a service should be able to publish from
        anywhere without needing to await, and the cost of an event should be
        close to the cost of appending to a list.
        """
        self._published += 1
        self._history.append((topic, payload))
        if len(self._history) > self._history_limit:
            del self._history[: len(self._history) - self._history_limit]

        for pattern, handlers in list(self._handlers.items()):
            if not _matches(topic, pattern):
                continue
            for handler in list(handlers):
                self._spawn(handler, topic, payload)

        for pattern, queue in list(self._queues):
            if not _matches(topic, pattern):
                continue
            try:
                queue.put_nowait((topic, payload))
            except asyncio.QueueFull:
                # Drop the oldest rather than the newest: for telemetry and
                # video the freshest item is the useful one.
                self._dropped += 1
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait((topic, payload))

    def _spawn(self, handler: Handler, topic: str, payload: Any) -> None:
        try:
            task = asyncio.get_running_loop().create_task(_guard(handler, topic, payload))
        except RuntimeError:
            # No loop (e.g. publishing from a sync test); run nothing rather
            # than exploding. Streams still receive the event.
            log.debug("publish(%s) outside an event loop; handler skipped", topic)
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # -- subscribing --------------------------------------------------------

    def subscribe(self, pattern: str, handler: Handler) -> Subscription:
        """Call ``handler(topic, payload)`` for every matching event."""
        self._handlers[pattern].append(handler)
        return Subscription(self, pattern, handler)

    def _remove(self, pattern: str, handler: Handler) -> None:
        handlers = self._handlers.get(pattern)
        if not handlers:
            return
        with contextlib.suppress(ValueError):
            handlers.remove(handler)
        if not handlers:
            self._handlers.pop(pattern, None)

    async def stream(self, pattern: str, *, maxsize: int = 64) -> AsyncIterator[tuple[str, Any]]:
        """Yield matching events. The queue is bounded and drops oldest."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        entry = (pattern, queue)
        self._queues.append(entry)
        try:
            while True:
                yield await queue.get()
        finally:
            with contextlib.suppress(ValueError):
                self._queues.remove(entry)

    # -- introspection ------------------------------------------------------

    def recent(self, pattern: str = "*", limit: int = 50) -> list[tuple[str, Any]]:
        """Last events matching ``pattern``, oldest first."""
        hits = [(t, p) for t, p in self._history if _matches(t, pattern)]
        return hits[-limit:]

    @property
    def stats(self) -> dict[str, int]:
        return {
            "published": self._published,
            "dropped": self._dropped,
            "handlers": sum(len(h) for h in self._handlers.values()),
            "streams": len(self._queues),
            "inflight": len(self._tasks),
        }

    async def drain(self) -> None:
        """Wait for in-flight handlers. Tests use this; the robot does not."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def aclose(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)
        self._handlers.clear()
        self._queues.clear()


async def _guard(handler: Handler, topic: str, payload: Any) -> None:
    try:
        await handler(topic, payload)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("subscriber for %s failed", topic)


def _matches(topic: str, pattern: str) -> bool:
    if pattern in ("*", topic):
        return True
    return fnmatch.fnmatchcase(topic, pattern)
