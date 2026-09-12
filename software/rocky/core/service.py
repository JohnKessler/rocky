"""Lifecycle scaffolding shared by every Rocky service."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rocky.config import Config
    from rocky.core.bus import EventBus


class Service:
    """A long-lived component with a start/stop lifecycle.

    Subclasses override :meth:`setup`, :meth:`run` and :meth:`teardown`.
    ``run`` is optional - a purely reactive service (one that only responds to
    bus events) just subscribes in ``setup`` and never implements ``run``.
    """

    name = "service"

    def __init__(self, bus: EventBus, config: Config) -> None:
        self.bus = bus
        self.config = config
        self.log = logging.getLogger(f"rocky.{self.name}")
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._started = False

    # -- to override --------------------------------------------------------

    async def setup(self) -> None:
        """Acquire resources and subscribe to the bus."""

    async def run(self) -> None:
        """Main loop. The default simply waits to be stopped."""
        await self._stopping.wait()

    async def teardown(self) -> None:
        """Release resources. Always called if ``setup`` succeeded."""

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        if self._started:
            return
        self.log.debug("starting")
        await self.setup()
        self._started = True
        self._task = asyncio.create_task(self._runner(), name=f"rocky-{self.name}")

    async def _runner(self) -> None:
        try:
            await self.run()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.log.exception("service crashed")

    async def stop(self) -> None:
        if not self._started:
            return
        self.log.debug("stopping")
        self._stopping.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        with contextlib.suppress(Exception):
            await self.teardown()
        self._started = False

    @property
    def running(self) -> bool:
        return self._started

    async def sleep(self, seconds: float) -> bool:
        """Sleep unless we are shutting down. Returns False if stopping."""
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)
        except TimeoutError:
            return True
        return False
