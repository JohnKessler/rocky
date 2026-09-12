"""Wiring.

The services know nothing about each other; this is the only module that knows
they all exist. That is the whole point of the bus - if you want to run Rocky
without a camera, or with the face on a second machine, you change this file
and nothing else.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import time
from pathlib import Path
from typing import Any

from rocky.audio.driver import AudioService
from rocky.brain.driver import BrainService
from rocky.config import Config
from rocky.core import events as ev
from rocky.core.bus import EventBus
from rocky.face.driver import FaceService
from rocky.motion.driver import MotionService
from rocky.vision.driver import VisionService

log = logging.getLogger("rocky.app")


class BusLogHandler(logging.Handler):
    """Mirrors log records onto the bus so the dashboard can show them."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__(level=logging.INFO)
        self.bus = bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.bus.publish(
                ev.LOG,
                ev.LogLine(
                    level=record.levelname,
                    logger=record.name,
                    message=self.format(record),
                ),
            )
        except Exception:  # pragma: no cover - logging must never raise
            pass


class RockyApp:
    """Owns the bus, the config and every service."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self.bus = EventBus()
        self.started_at = time.time()

        Path(self.config.state_dir).mkdir(parents=True, exist_ok=True)

        self.motion = MotionService(self.bus, self.config)
        self.face = FaceService(self.bus, self.config)
        self.vision = VisionService(self.bus, self.config)
        self.audio = AudioService(self.bus, self.config)
        self.brain = BrainService(
            self.bus, self.config,
            frame_source=self.vision.latest_frame,
            status_source=self.status,
        )
        self.services = [self.motion, self.face, self.vision, self.audio, self.brain]
        self._telemetry_task: asyncio.Task | None = None
        self._log_handler: BusLogHandler | None = None

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        self._attach_logging()
        log.info(
            "Rocky %s starting on %s",
            __import__("rocky").__version__, platform.node(),
        )
        for service in self.services:
            try:
                await service.start()
            except Exception:
                log.exception("%s failed to start", service.name)
        self._telemetry_task = asyncio.create_task(self._telemetry_loop(), name="rocky-telemetry")

        # Rocky wakes up rather than simply appearing.
        self.bus.publish(ev.EXPRESSION, ev.Expression("sleepy", 1.0))
        await asyncio.sleep(0.6)
        self.bus.publish(ev.EXPRESSION, ev.Expression("content", 1.0))
        self.bus.publish(ev.GESTURE, ev.Gesture("perk", 0.7))
        self.bus.publish(ev.CHIRP, ev.Chirp("greeting"))

    async def stop(self) -> None:
        log.info("Rocky stopping")
        if self._telemetry_task:
            self._telemetry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._telemetry_task
            self._telemetry_task = None
        for service in reversed(self.services):
            with contextlib.suppress(Exception):
                await service.stop()
        await self.bus.aclose()
        self._detach_logging()

    def _attach_logging(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)-7s %(name)-14s %(message)s",
            datefmt="%H:%M:%S",
        )
        self._log_handler = BusLogHandler(self.bus)
        self._log_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(self._log_handler)

    def _detach_logging(self) -> None:
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None

    # -- telemetry ----------------------------------------------------------

    async def _telemetry_loop(self) -> None:
        while True:
            period = 1.0 / max(0.2, self.config.web.telemetry_hz)
            try:
                self.bus.publish(ev.TELEMETRY, ev.Telemetry(self.status()))
            except Exception:
                log.exception("telemetry failed")
            await asyncio.sleep(period)

    def status(self) -> dict[str, Any]:
        """One snapshot of the whole robot, for the dashboard and the
        ``check_self`` tool."""
        return {
            "uptime_s": round(time.time() - self.started_at, 1),
            "cpu_temp_c": read_cpu_temperature(),
            "load": _load_average(),
            "host": platform.node(),
            "bus": self.bus.stats,
            "motion": self.motion.snapshot(),
            "face": self.face.snapshot(),
            "vision": self.vision.snapshot(),
            "audio": self.audio.snapshot(),
            "brain": self.brain.snapshot(),
        }

    # -- convenience used by the dashboard and the CLI ----------------------

    async def say(self, text: str) -> None:
        self.bus.publish(ev.UTTERANCE, ev.Utterance(text=text))

    async def ask(self, text: str) -> str:
        """Put text in as though it had been heard."""
        return await self.brain.handle_input(text)

    async def run_forever(self) -> None:
        await self.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        finally:
            await self.stop()


def read_cpu_temperature() -> float | None:
    """Pi thermal zone, in Celsius."""
    for path in (
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
    ):
        try:
            with open(path) as handle:
                return round(int(handle.read().strip()) / 1000.0, 1)
        except (OSError, ValueError):
            continue
    return None


def _load_average() -> list[float]:
    try:
        return [round(v, 2) for v in os.getloadavg()]
    except (OSError, AttributeError):  # pragma: no cover - not on all platforms
        return []
