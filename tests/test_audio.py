"""Chirps, voice activity, and utterance gating."""

from __future__ import annotations

import math
import random

import pytest
from rocky.audio.chirps import MOTIF_NAMES, MOTIFS, motif_for_expression, render
from rocky.audio.devices import SimAudioIO, pitch_shift, resample, rms
from rocky.audio.vad import EnergyVAD, UtteranceGate
from rocky.config import ChirpConfig

SR = 16000


def voice(n: int, amp: float = 0.2, freq: float = 180.0) -> list[float]:
    return [math.sin(2 * math.pi * freq * i / SR) * amp for i in range(n)]


def room_tone(n: int, amp: float = 0.002) -> list[float]:
    return [random.uniform(-amp, amp) for _ in range(n)]


class TestChirps:
    @pytest.mark.parametrize("name", list(MOTIF_NAMES))
    def test_every_motif_renders(self, name):
        samples = render(name, ChirpConfig(), SR)
        assert samples
        assert max(abs(v) for v in samples) <= 1.0

    def test_volume_scales_the_peak(self):
        quiet = render("greeting", ChirpConfig(volume=0.2), SR)
        loud = render("greeting", ChirpConfig(volume=0.8), SR)
        assert max(abs(v) for v in loud) > max(abs(v) for v in quiet)

    def test_disabling_chirps_produces_silence(self):
        assert render("greeting", ChirpConfig(enabled=False), SR) == []

    def test_an_unknown_motif_is_silent_rather_than_fatal(self):
        assert render("fanfare", ChirpConfig(), SR) == []

    def test_root_note_changes_the_pitch(self):
        """Same motif, different root, must not be the same audio."""
        low = render("affirm", ChirpConfig(base_hz=150), SR)
        high = render("affirm", ChirpConfig(base_hz=300), SR)
        assert low != high

    def test_it_starts_and_ends_quietly(self):
        """An envelope that does not open and close from zero clicks."""
        samples = render("greeting", ChirpConfig(), SR)
        assert abs(samples[0]) < 0.02
        assert abs(samples[-1]) < 0.05

    def test_expressions_map_to_motifs(self):
        assert motif_for_expression("delighted") in MOTIF_NAMES
        assert motif_for_expression("neutral") is None

    def test_every_motif_means_something(self):
        for m in MOTIFS.values():
            assert m.meaning


class TestVAD:
    def test_speech_is_detected_over_room_tone(self):
        vad = EnergyVAD()
        for _ in range(20):
            vad.is_speech(room_tone(480), SR)
        assert vad.is_speech(voice(480), SR)

    def test_room_tone_is_not_speech(self):
        vad = EnergyVAD()
        for _ in range(20):
            vad.is_speech(room_tone(480), SR)
        assert not vad.is_speech(room_tone(480), SR)

    def test_the_noise_floor_adapts_upward(self):
        """A fan switching on must not deafen Rocky permanently."""
        vad = EnergyVAD()
        for _ in range(20):
            vad.is_speech(room_tone(480, 0.001), SR)
        quiet_floor = vad.noise_floor
        for _ in range(400):
            vad.is_speech(room_tone(480, 0.05), SR)
        assert vad.noise_floor > quiet_floor

    def test_it_does_not_fire_before_it_has_warmed_up(self):
        vad = EnergyVAD()
        assert not vad.is_speech(voice(480), SR)


class TestUtteranceGate:
    def test_silence_ends_an_utterance(self):
        gate = UtteranceGate(SR, silence_s=0.3, max_s=10)
        for _ in range(40):
            assert gate.push(voice(480), True) is None
        result = None
        for _ in range(20):
            result = gate.push(room_tone(480), False)
            if result:
                break
        assert result and len(result) / SR == pytest.approx(1.5, abs=0.2)

    def test_a_short_pause_does_not_split_a_sentence(self):
        gate = UtteranceGate(SR, silence_s=0.5, max_s=10)
        for _ in range(20):
            gate.push(voice(480), True)
        for _ in range(5):  # 150ms gap, well under the threshold
            assert gate.push(room_tone(480), False) is None
        for _ in range(20):
            assert gate.push(voice(480), True) is None
        assert gate.active

    def test_it_cuts_off_at_the_maximum(self):
        """A stuck-open microphone must not buffer forever."""
        gate = UtteranceGate(SR, silence_s=5, max_s=1.0)
        result = None
        for _ in range(100):
            result = gate.push(voice(480), True)
            if result:
                break
        assert result and len(result) / SR <= 1.1

    def test_a_cough_is_discarded(self):
        gate = UtteranceGate(SR, silence_s=0.1, max_s=10)
        gate.push(voice(480), True)
        for _ in range(10):
            result = gate.push(room_tone(480), False)
            if result is not None:
                pytest.fail("a 30ms blip should not become an utterance")
        assert not gate.active

    def test_reset_clears_the_buffer(self):
        gate = UtteranceGate(SR, silence_s=0.3, max_s=10)
        for _ in range(10):
            gate.push(voice(480), True)
        gate.reset()
        assert gate.duration == 0 and not gate.active


class TestDevices:
    def test_sim_io_round_trip(self):
        io = SimAudioIO(SR, 480)
        assert len(io.read()) == 480
        io.inject([0.5] * 480)
        assert rms(io.read()) == pytest.approx(0.5)
        assert io.play([0.0] * SR) == pytest.approx(1.0)

    def test_resample_changes_length(self):
        assert len(resample([0.0] * 1000, 2.0)) == 500

    def test_pitch_shift_preserves_duration(self):
        """The face's mouth and the motion gestures are timed off the audio
        length, so a shift that changes duration desynchronises them."""
        signal = voice(SR)
        for semitones in (-4, -1.5, 3):
            assert len(pitch_shift(signal, semitones, SR)) == len(signal)

    def test_no_shift_is_a_no_op(self):
        signal = voice(100)
        assert pitch_shift(signal, 0.0, SR) == signal
