"""Configuration: bounds, dotted paths, round-tripping."""

from __future__ import annotations

import pytest

from rocky.config import Config


class TestDottedPaths:
    def test_get_and_set(self, config: Config):
        assert config.get_path("motion.pan.channel") == 0
        assert config.set_path("motion.pan.channel", 3) == 3
        assert config.motion.pan.channel == 3

    def test_unknown_path_is_rejected(self, config: Config):
        with pytest.raises(AttributeError):
            config.set_path("motion.pan.nonsense", 1)

    def test_out_of_range_is_rejected(self, config: Config):
        """A slider must not be able to drive a servo past its limits."""
        with pytest.raises(ValueError):
            config.set_path("motion.tilt.max_deg", 9999)
        assert config.motion.tilt.max_deg == 26.0

    def test_float_is_coerced_for_int_fields(self, config: Config):
        assert config.set_path("face.fps", 30.0) == 30
        assert isinstance(config.face.fps, int)

    @pytest.mark.parametrize("path,value", [
        ("identity.traits.curiosity", 1.5),
        ("audio.tts.volume", -0.2),
        ("web.port", 99999),
        ("motion.pan.pulse_min_us", 100),
    ])
    def test_bounds_are_enforced(self, config: Config, path, value):
        with pytest.raises(ValueError):
            config.set_path(path, value)


class TestSchema:
    def test_every_scalar_is_described(self, config: Config):
        values, schema = config.flatten(), config.schema_for_ui()
        assert set(values) == set(schema)
        assert len(values) > 100

    def test_bounded_fields_expose_their_bounds(self, config: Config):
        meta = config.schema_for_ui()["motion.tracking.gain"]
        assert meta["type"] == "float"
        assert meta["min"] == 0 and meta["max"] == 3

    def test_literal_fields_expose_choices(self, config: Config):
        assert config.schema_for_ui()["brain.effort"]["choices"] == [
            "low", "medium", "high", "xhigh", "max"
        ]

    def test_help_text_is_carried_through(self, config: Config):
        assert "help" in config.schema_for_ui()["motion.idle_torque_off_s"]


class TestPersistence:
    def test_round_trip(self, config: Config, tmp_path):
        config.set_path("identity.name", "Rocky")
        config.set_path("motion.tilt.max_deg", 20)
        config.set_path("audio.chirps.base_hz", 220.0)
        config.set_path("face.fullscreen", False)
        path = config.save(tmp_path / "c.toml")

        loaded = Config.load(path)
        assert loaded.motion.tilt.max_deg == 20
        assert loaded.audio.chirps.base_hz == 220.0
        assert loaded.face.fullscreen is False

    def test_quotes_survive_the_writer(self, config: Config, tmp_path):
        config.set_path("identity.owner_name", 'Jo "The Spanner" Smith')
        loaded = Config.load(config.save(tmp_path / "c.toml"))
        assert loaded.identity.owner_name == 'Jo "The Spanner" Smith'

    def test_missing_file_gives_defaults(self, tmp_path):
        assert Config.load(tmp_path / "nope.toml").identity.name == "Rocky"


class TestEnvironment:
    def test_env_overrides_are_applied(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ROCKY_MOTION__PAN__MAX_SPEED_DPS", "42")
        monkeypatch.setenv("ROCKY_FACE__FULLSCREEN", "false")
        cfg = Config.load(tmp_path / "nope.toml")
        assert cfg.motion.pan.max_speed_dps == 42
        assert cfg.face.fullscreen is False

    def test_a_nonsense_override_is_ignored_not_fatal(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ROCKY_MOTION__PAN__MAX_SPEED_DPS", "banana")
        Config.load(tmp_path / "nope.toml")  # must not raise
