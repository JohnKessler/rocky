"""Whole-robot behaviour, in simulation.

These are the tests that would have caught the interesting bugs: they boot
every service, let the closed-loop simulator run, and assert on what Rocky
actually does rather than on what any one component returns.
"""

from __future__ import annotations

import asyncio

import pytest
from rocky.app import RockyApp
from rocky.core import events as ev


@pytest.fixture
async def rocky(config):
    config.motion.idle.enabled = False
    app = RockyApp(config)
    await app.start()
    yield app
    await app.stop()


@pytest.fixture
async def events(config):
    """A started robot plus everything published on ITS bus.

    The app builds its own bus, so a collector attached to the bare `bus`
    fixture would sit there watching nothing.
    """
    config.motion.idle.enabled = False
    app = RockyApp(config)
    collected: list[tuple[str, object]] = []

    async def handler(topic, payload):
        collected.append((topic, payload))

    app.bus.subscribe("*", handler)
    await app.start()
    yield app, collected
    await app.stop()


class TestBoot:
    async def test_every_service_starts(self, rocky: RockyApp):
        assert all(service.running for service in rocky.services)

    async def test_every_backend_reports_simulated(self, rocky: RockyApp):
        status = rocky.status()
        assert status["motion"]["backend"] == "SimServoBackend"
        assert status["vision"]["camera"] == "SimCamera"
        assert status["face"]["renderer"] == "HeadlessRenderer"
        assert status["audio"]["io"] == "SimAudioIO"

    async def test_it_wakes_up_rather_than_appearing(self, events):
        _, collected = events
        await asyncio.sleep(0.9)
        expressions = [p.name for t, p in collected if t == ev.EXPRESSION]
        assert "sleepy" in expressions and "content" in expressions

    async def test_shutdown_releases_the_servos(self, config):
        """Leaving a servo energised after exit means it hums on the desk
        until someone pulls the plug."""
        app = RockyApp(config)
        await app.start()
        app.motion.jog(pan=20)
        await asyncio.sleep(0.3)
        backend = app.motion.backend
        await app.stop()
        assert not any(backend.energised.values())


class TestFaceTracking:
    async def test_the_head_turns_to_centre_a_face(self, rocky: RockyApp):
        """The simulator is closed-loop, so this genuinely exercises the
        control law: the head turns, which moves the subject in frame, which
        changes the error."""
        rocky.vision.camera.drift = False
        azimuth, _, _ = rocky.vision.camera.subject_bearing()

        for _ in range(60):
            await asyncio.sleep(0.05)
            if abs(rocky.motion.pan.position - azimuth) < 3.0:
                break

        assert rocky.motion.pan.position == pytest.approx(azimuth, abs=3.0)
        position = rocky.vision.camera.subject_position()
        assert position is not None
        assert position[0] == pytest.approx(0.5, abs=0.06)

    async def test_it_settles_rather_than_hunting(self, rocky: RockyApp):
        """A tracker that keeps correcting reads as twitchy and grinds the
        gears. Once locked, the head should go quiet."""
        rocky.vision.camera.drift = False
        for _ in range(70):
            await asyncio.sleep(0.05)
            if rocky.motion.pan.at_rest and abs(rocky.motion.pan.position) > 5:
                break

        samples = []
        for _ in range(20):
            await asyncio.sleep(0.05)
            samples.append(rocky.motion.pan.position)
        assert max(samples) - min(samples) < 1.5

    async def test_it_never_exceeds_the_mechanical_envelope(self, rocky: RockyApp):
        for _ in range(40):
            await asyncio.sleep(0.05)
            assert -100.0 <= rocky.motion.pan.position <= 100.0
            assert -26.0 <= rocky.motion.tilt.position <= 26.0


class TestIdleTorque:
    async def test_servos_release_when_the_head_settles(self, config):
        """This one setting is the difference between a robot you leave out
        and one you put away."""
        config.motion.idle.enabled = False
        config.motion.idle_torque_off_s = 0.3
        config.vision.enabled = False
        app = RockyApp(config)
        await app.start()
        try:
            app.motion.jog(pan=30)
            await asyncio.sleep(0.2)
            assert app.motion.snapshot()["torque"] is True
            for _ in range(40):
                await asyncio.sleep(0.1)
                if app.motion.snapshot()["torque"] is False:
                    break
            assert app.motion.snapshot()["torque"] is False
        finally:
            await app.stop()

    async def test_a_new_command_re_energises(self, config):
        config.motion.idle.enabled = False
        config.motion.idle_torque_off_s = 0.2
        config.vision.enabled = False
        app = RockyApp(config)
        await app.start()
        try:
            # The wake-up gesture at boot keeps the servos alive for a moment,
            # so wait for it to finish rather than guessing a duration.
            for _ in range(40):
                await asyncio.sleep(0.1)
                if app.motion.snapshot()["torque"] is False:
                    break
            assert app.motion.snapshot()["torque"] is False

            app.motion.jog(pan=25)
            await asyncio.sleep(0.2)
            assert app.motion.snapshot()["torque"] is True
        finally:
            await app.stop()


class TestConversationPath:
    async def test_injected_speech_reaches_the_brain(self, rocky: RockyApp, monkeypatch):
        """Injection enters at exactly the point a real transcript would, so
        this exercises the whole path without a microphone."""
        seen: list[str] = []

        async def fake_handle(text: str) -> str:
            seen.append(text)
            return ""

        monkeypatch.setattr(rocky.brain, "handle_input", fake_handle)
        rocky.audio.inject_text("what can you see")
        await asyncio.sleep(0.2)
        await rocky.bus.drain()
        assert seen == ["what can you see"]

    async def test_speaking_closes_the_microphone(self, rocky: RockyApp):
        """Rocky hears itself through the air; without this it transcribes its
        own sentences and answers them."""
        states: list[bool] = []

        async def watch(topic, payload):
            states.append(rocky.audio._mic_open)

        rocky.audio.io.realtime = True   # this test is about timing
        rocky.bus.subscribe(ev.SPEAKING, watch)
        task = asyncio.create_task(rocky.audio.speak("Good, good, good. I am awake."))
        await asyncio.sleep(0.25)
        assert rocky.audio._speaking is True, "the mic must be shut while Rocky talks"
        assert rocky.audio._mic_open is False
        await task
        assert rocky.audio._speaking is False

    async def test_a_reply_opens_a_follow_up_window(self, rocky: RockyApp):
        await rocky.audio.speak("I am here.")
        assert rocky.audio._mic_open is True

    async def test_an_over_long_reply_is_cut_at_a_sentence(self, rocky: RockyApp):
        rocky.config.brain.reply_char_limit = 80
        long = "This is one sentence. This is another sentence. " * 5
        trimmed = rocky.brain._trim_reply(long)
        assert len(trimmed) <= 80 and trimmed.endswith(".")


class TestArrival:
    async def test_rocky_notices_someone_arrive(self, events):
        rocky, collected = events
        await asyncio.sleep(0.6)
        await rocky.bus.drain()
        chirps = [p.motif for t, p in collected if t == ev.CHIRP]
        assert "greeting" in chirps


class TestTelemetry:
    async def test_status_is_json_serialisable(self, rocky: RockyApp):
        """The dashboard sends this over a websocket; anything unserialisable
        silently kills the connection."""
        import json

        json.dumps(rocky.status(), default=str)

    async def test_telemetry_is_published_periodically(self, events):
        rocky, collected = events
        await asyncio.sleep(0.8)
        await rocky.bus.drain()
        assert len([1 for t, _ in collected if t == ev.TELEMETRY]) >= 2
