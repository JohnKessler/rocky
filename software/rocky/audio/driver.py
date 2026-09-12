"""The audio service: hearing and speaking."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from rocky.audio import chirps
from rocky.audio.devices import AudioIO, make_audio_io, rms
from rocky.audio.stt import STT, ScriptedSTT, make_stt
from rocky.audio.tts import TTS, make_tts, tone
from rocky.audio.vad import UtteranceGate, make_vad
from rocky.audio.wake import DebouncedWake, make_wake
from rocky.core import events as ev
from rocky.core.service import Service


class AudioService(Service):
    """Wake word, speech recognition, speech synthesis, chirps.

    One capture loop owns the microphone. It is closed while Rocky is talking -
    a desk robot hears itself through the air perfectly well, and without that
    gate Rocky transcribes its own sentences and answers them.
    """

    name = "audio"

    def __init__(self, bus, config) -> None:
        super().__init__(bus, config)
        self.io: AudioIO | None = None
        self.stt: STT | None = None
        self.tts: TTS | None = None
        self.wake: DebouncedWake | None = None
        self._vad = None
        self._gate: UtteranceGate | None = None

        self._mic_open = False
        self._mic_open_until = 0.0
        self._speaking = False
        self._level = 0.0
        self._pending_text: list[str] = []
        self._utterances = 0
        self._last_transcript = ""
        self._speak_lock = asyncio.Lock()

    # -- lifecycle ----------------------------------------------------------

    async def setup(self) -> None:
        cfg = self.config.audio
        frame_size = int(cfg.sample_rate * cfg.frame_ms / 1000)
        self.io = make_audio_io(
            self.config.hardware.audio, cfg.sample_rate, frame_size,
            cfg.input_device, cfg.output_device,
            realtime=self.config.hardware.sim_realtime_audio,
        )
        self.wake = make_wake(cfg.wake)
        self._vad = make_vad(cfg.stt.vad_threshold)
        self._gate = UtteranceGate(cfg.sample_rate, cfg.stt.silence_s, cfg.stt.max_utterance_s)
        self.stt = make_stt(cfg.stt)
        self.tts = make_tts(cfg.tts)
        self.log.info(
            "io=%s wake=%s vad=%s stt=%s tts=%s",
            self.io.kind, self.wake.kind, self._vad.kind, self.stt.kind, self.tts.kind,
        )
        self.bus.subscribe(ev.UTTERANCE, self._on_utterance)
        self.bus.subscribe(ev.CHIRP, self._on_chirp)

    async def teardown(self) -> None:
        for component in (self.stt, self.tts, self.io):
            if component:
                component.close()
        self.io = self.stt = self.tts = None

    # -- capture loop -------------------------------------------------------

    async def run(self) -> None:
        cfg = self.config.audio
        frame_s = cfg.frame_ms / 1000.0
        while True:
            if not cfg.enabled or self.io is None:
                if not await self.sleep(0.2):
                    return
                continue
            try:
                await self._capture_once()
            except Exception:
                self.log.exception("capture failed")
            # SoundDeviceIO.read blocks for a frame; the simulator does not,
            # so pace it here to keep both running at the same rate.
            if not await self.sleep(frame_s if self.io.kind == "SimAudioIO" else 0.001):
                return

    async def _capture_once(self) -> None:
        assert self.io is not None and self.wake is not None and self._gate is not None
        cfg = self.config.audio

        frame = await asyncio.to_thread(self.io.read)
        if cfg.input_gain != 1.0:
            frame = [v * cfg.input_gain for v in frame]
        self._level = rms(frame)

        if self._speaking:
            # Deaf while talking, and the gate is reset so the tail of Rocky's
            # own sentence is not waiting in the buffer afterwards.
            self._gate.reset()
            return

        now = time.time()

        if not self._mic_open:
            score = self.wake.push(frame, cfg.sample_rate)
            if score is not None:
                self._open_mic("wake word", score)
            return

        if now > self._mic_open_until:
            self._close_mic("timed out")
            return

        speech = self._vad.is_speech(frame, cfg.sample_rate)
        utterance = self._gate.push(frame, speech)
        if utterance is None:
            return

        self._utterances += 1
        transcript = await asyncio.to_thread(self.stt.transcribe, utterance, cfg.sample_rate)
        text = transcript.text.strip()
        self._last_transcript = text
        if not text:
            self.log.debug("empty transcript; staying open")
            return

        self.log.info("heard: %s", text)
        self.bus.publish(
            ev.SPEECH,
            ev.Speech(
                text=text, final=True,
                confidence=transcript.confidence, duration_s=transcript.duration_s,
            ),
        )
        self._close_mic("utterance complete")

    def _open_mic(self, reason: str, score: float = 1.0) -> None:
        self._mic_open = True
        self._mic_open_until = time.time() + self.config.audio.stt.max_utterance_s + 2.0
        self._gate.reset()
        self.bus.publish(ev.WAKE, ev.Wake(keyword=self.config.identity.wake_word, confidence=score))
        self.bus.publish(ev.LISTENING, ev.Listening(True, reason))
        if self.config.audio.chirps.enabled:
            self.bus.publish(ev.CHIRP, ev.Chirp("acknowledge"))

    def _close_mic(self, reason: str) -> None:
        self._mic_open = False
        self._gate.reset()
        self.bus.publish(ev.LISTENING, ev.Listening(False, reason))

    # -- output -------------------------------------------------------------

    async def _on_utterance(self, _topic: str, e: ev.Utterance) -> None:
        await self.speak(e.text, expression=e.expression)

    async def _on_chirp(self, _topic: str, e: ev.Chirp) -> None:
        await self.play_motif(e.motif)

    async def play_motif(self, name: str) -> None:
        cfg = self.config.audio
        if not cfg.chirps.enabled or self.io is None:
            return
        samples = chirps.render(name, cfg.chirps, cfg.sample_rate)
        if samples:
            await asyncio.to_thread(self.io.play, samples)

    async def speak(self, text: str, expression: str | None = None) -> float:
        """Say something. Returns how long the audio ran for."""
        text = text.strip()
        if not text or self.io is None or self.tts is None:
            return 0.0

        cfg = self.config.audio
        async with self._speak_lock:
            self._speaking = True
            # Shut the mic explicitly rather than relying on the capture loop
            # skipping frames, so the reported state is honest: the dashboard
            # should never show "listening" while Rocky is talking.
            if self._mic_open:
                self._close_mic("speaking")
            self.bus.publish(ev.SPEAKING, ev.Speaking(True, text))
            total = 0.0
            try:
                if cfg.chirps.enabled and cfg.chirps.before_speech:
                    # Match the chirp to the feeling if the brain named one,
                    # so the chord and the face agree.
                    motif = (chirps.motif_for_expression(expression or "") or "acknowledge")
                    total += await asyncio.to_thread(
                        self.io.play, chirps.render(motif, cfg.chirps, cfg.sample_rate)
                    )

                samples = await asyncio.to_thread(self.tts.synthesize, text, cfg.sample_rate)
                if samples:
                    total += await asyncio.to_thread(self.io.play, samples)

                if cfg.chirps.enabled and cfg.chirps.after_speech:
                    total += await asyncio.to_thread(
                        self.io.play, chirps.render("acknowledge", cfg.chirps, cfg.sample_rate)
                    )
            finally:
                self._speaking = False
                self.bus.publish(ev.SPEAKING, ev.Speaking(False, text))

            # Hold the mic open briefly so a follow-up needs no wake word.
            window = cfg.wake.open_mic_after_reply_s
            if window > 0:
                self._mic_open = True
                self._mic_open_until = time.time() + window
                self._gate.reset()
                self.bus.publish(ev.LISTENING, ev.Listening(True, "follow-up window"))
        return total

    # -- injection, used by the dashboard and the tests ---------------------

    def inject_text(self, text: str) -> None:
        """Push text in as if it had been heard. The rest of the pipeline
        cannot tell the difference, which is what makes the dashboard's text
        box a genuine test of the whole conversation path."""
        text = text.strip()
        if not text:
            return
        self._last_transcript = text
        self._utterances += 1
        if isinstance(self.stt, ScriptedSTT):
            self.stt.say(text)
        self.bus.publish(ev.SPEECH, ev.Speech(text=text, final=True, confidence=1.0))

    async def test_tone(self, freq: float = 440.0, seconds: float = 0.4) -> None:
        if self.io:
            await asyncio.to_thread(
                self.io.play, tone(freq, seconds, self.config.audio.sample_rate)
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "io": self.io.kind if self.io else "none",
            "wake": self.wake.kind if self.wake else "none",
            "stt": self.stt.kind if self.stt else "none",
            "tts": self.tts.kind if self.tts else "none",
            "mic_open": self._mic_open,
            "speaking": self._speaking,
            "level": round(self._level, 5),
            "wake_score": round(self.wake.last_score, 3) if self.wake else 0.0,
            "utterances": self._utterances,
            "last_transcript": self._last_transcript,
        }
