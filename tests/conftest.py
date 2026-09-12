"""Shared fixtures.

Every test runs against the simulated backends, so the suite passes on a
laptop, in CI, and on the robot itself.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from rocky.config import Config
from rocky.core.bus import EventBus


@pytest.fixture
def config(tmp_path: Path) -> Config:
    cfg = Config()
    for field in ("servos", "camera", "display", "audio"):
        setattr(cfg.hardware, field, "sim")
    cfg.state_dir = str(tmp_path)
    cfg.memory.path = str(tmp_path / "rocky.db")
    cfg.audio.stt.backend = "none"
    cfg.audio.tts.backend = "none"
    cfg.audio.wake.backend = "none"
    cfg.brain.scene_in_context = False
    # Let simulated playback run at full speed; the one test that is actually
    # about speaking timing turns it back on for itself.
    cfg.hardware.sim_realtime_audio = False
    cfg.web.enabled = False
    cfg.log_level = "ERROR"
    return cfg


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def collected(bus: EventBus):
    """Collect every event published during a test."""
    events: list[tuple[str, object]] = []

    async def handler(topic, payload):
        events.append((topic, payload))

    bus.subscribe("*", handler)
    return events


async def settle(bus: EventBus, seconds: float = 0.05) -> None:
    """Let queued handlers run."""
    await asyncio.sleep(seconds)
    await bus.drain()
