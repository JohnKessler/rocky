"""Rocky's configuration.

One nested pydantic model holds everything. The dashboard edits it live by
dotted path (``motion.pan.max_speed``), so every field that is safe to change
while Rocky is running is a plain scalar with explicit bounds - the bounds are
what stop a slider from driving a servo into its end stop.

Precedence, lowest to highest:

    model defaults  ->  config.toml  ->  ROCKY_* environment  ->  live edits

Live edits are written back to ``config.toml`` only when you press Save in the
dashboard, so a bad experiment disappears on restart.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONFIG_PATH = Path(os.environ.get("ROCKY_CONFIG", "config.toml"))


class _Base(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")


# ---------------------------------------------------------------------------
# identity and personality
# ---------------------------------------------------------------------------


class Traits(_Base):
    """Personality dials, 0.0 to 1.0.

    These are not decoration. Each one is consumed somewhere concrete: the
    persona prompt quotes them, the face picks blink and saccade rates from
    ``energy``, and the motion service scales gesture amplitude by it. Turning
    a dial in the dashboard changes behaviour within a second or two.
    """

    curiosity: float = Field(0.75, ge=0, le=1, description="How readily Rocky looks at new things and asks about them")
    chattiness: float = Field(0.45, ge=0, le=1, description="How often Rocky speaks unprompted")
    playfulness: float = Field(0.70, ge=0, le=1, description="Humour, teasing, and silly chirps")
    warmth: float = Field(0.80, ge=0, le=1, description="How openly Rocky expresses fondness")
    formality: float = Field(0.15, ge=0, le=1, description="Sentence register; Rocky's speech is plain by design")
    energy: float = Field(0.60, ge=0, le=1, description="Movement amplitude, blink rate, speech pace")
    focus: float = Field(0.55, ge=0, le=1, description="How long Rocky stays on one subject before drifting")


class Identity(_Base):
    name: str = "Rocky"
    wake_word: str = "hey rocky"
    # Shown in the dashboard header; also given to the model as context.
    owner_name: str = ""
    traits: Traits = Field(default_factory=Traits)


# ---------------------------------------------------------------------------
# brain
# ---------------------------------------------------------------------------


class BrainConfig(_Base):
    model: str = "claude-opus-5"
    max_tokens: int = Field(1024, ge=64, le=32000)
    # A spoken companion answers in a sentence or two, so low effort keeps the
    # gap between "you stop talking" and "Rocky starts talking" short. Raise it
    # if you start asking Rocky harder questions.
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    thinking: bool = True
    # Server-side refusal fallbacks. Harmless if your account lacks the beta -
    # the client retries once without it and remembers.
    refusal_fallbacks: bool = True

    history_turns: int = Field(12, ge=2, le=60, description="Conversation turns kept in context")
    idle_prompt_seconds: float = Field(0.0, ge=0, description="Speak unprompted after this long; 0 disables")
    scene_in_context: bool = Field(True, description="Give the model what the camera sees")
    max_tool_iterations: int = Field(6, ge=1, le=20)

    reply_char_limit: int = Field(320, ge=40, le=2000, description="Hard cap on a spoken reply")


class MemoryConfig(_Base):
    enabled: bool = True
    path: str = "var/rocky.db"
    max_facts: int = Field(500, ge=10, le=10000)
    recall_limit: int = Field(8, ge=1, le=40)


# ---------------------------------------------------------------------------
# face
# ---------------------------------------------------------------------------


class Palette(_Base):
    background: str = "#05070d"
    iris: str = "#6fd3e7"
    iris_inner: str = "#bff0fa"
    glow: str = "#1c6b7d"
    mouth: str = "#6fd3e7"
    blush: str = "#e0715f"


class FaceConfig(_Base):
    width: int = Field(720, ge=120, le=2048)
    height: int = Field(720, ge=120, le=2048)
    fps: int = Field(45, ge=10, le=120)
    fullscreen: bool = True
    # Round panels crop to a circle; set False for a square/rect display.
    circular_mask: bool = True

    eye_spacing: float = Field(0.30, ge=0.10, le=0.60, description="Eye separation as a fraction of width")
    eye_radius: float = Field(0.135, ge=0.03, le=0.30)
    eye_y: float = Field(0.46, ge=0.10, le=0.90, description="Eye centre height as a fraction")
    pupil_track: float = Field(0.35, ge=0, le=1, description="How far the eyes follow what Rocky looks at")

    blink_min_s: float = Field(2.4, ge=0.3, le=30)
    blink_max_s: float = Field(7.0, ge=0.5, le=60)
    blink_duration_s: float = Field(0.13, ge=0.03, le=0.6)
    saccade_rate: float = Field(0.55, ge=0, le=5, description="Idle eye darts per second")

    expression_blend_s: float = Field(0.28, ge=0.01, le=3.0, description="Time to cross-fade expressions")
    resting_expression: str = "content"
    idle_decay_s: float = Field(14.0, ge=1, le=300, description="Time before drifting back to resting")

    palette: Palette = Field(default_factory=Palette)
    preview_fps: int = Field(12, ge=1, le=30, description="Face mirror rate for the dashboard")


# ---------------------------------------------------------------------------
# motion
# ---------------------------------------------------------------------------


class AxisConfig(_Base):
    """One servo axis.

    ``min_deg``/``max_deg`` are the soft limits in Rocky's own frame, where 0
    is straight ahead. They must stay inside whatever the printed hard stops
    allow - the stops exist so a bad number here cannot wring the harness, but
    hitting them still stalls the servo.
    """

    channel: int = Field(0, ge=0, le=15)
    # The outer bounds here only catch typos. The real protection is the
    # mechanical envelope in rocky.motion.kinematics, which clamps whatever
    # this file says, and the printed hard stops behind that.
    min_deg: float = Field(-100.0, ge=-150, le=150)
    max_deg: float = Field(100.0, ge=-150, le=150)
    centre_trim_deg: float = Field(0.0, ge=-30, le=30, description="Mechanical zero correction")
    invert: bool = False

    pulse_min_us: int = Field(500, ge=400, le=1500)
    pulse_max_us: int = Field(2500, ge=1500, le=2800)
    range_deg: float = Field(180.0, gt=30, le=360, description="Servo travel between the two pulse limits")

    max_speed_dps: float = Field(150.0, gt=1, le=900, description="Degrees per second ceiling")
    max_accel_dps2: float = Field(600.0, gt=1, le=6000)

    @field_validator("max_deg")
    @classmethod
    def _ordered(cls, v: float, info: Any) -> float:
        lo = info.data.get("min_deg")
        if lo is not None and v <= lo:
            raise ValueError("max_deg must exceed min_deg")
        return v


class TrackingConfig(_Base):
    enabled: bool = True
    # Proportional-only tracking with a deadband reads as calm attention;
    # adding much derivative gain makes Rocky twitchy and unsettling.
    gain: float = Field(0.55, ge=0, le=3)
    damping: float = Field(0.12, ge=0, le=2)
    deadband: float = Field(0.045, ge=0, le=0.4, description="Ignore offsets smaller than this, normalised")
    lost_target_hold_s: float = Field(2.5, ge=0, le=30)
    # Rocky looks at the face's eyes, a little above the box centre.
    vertical_bias: float = Field(-0.08, ge=-0.5, le=0.5)


class IdleMotion(_Base):
    enabled: bool = True
    scan_interval_s: float = Field(22.0, ge=2, le=600)
    scan_amplitude_deg: float = Field(28.0, ge=0, le=120)
    micro_move_interval_s: float = Field(5.0, ge=0.5, le=120)
    micro_move_deg: float = Field(2.2, ge=0, le=20, description="Small settling drifts, so Rocky never looks frozen")


class MotionConfig(_Base):
    enabled: bool = True
    i2c_address: int = Field(0x40, ge=0x40, le=0x7F)
    pwm_frequency: int = Field(50, ge=40, le=400)

    pan: AxisConfig = Field(default_factory=lambda: AxisConfig(channel=0, min_deg=-100, max_deg=100))
    tilt: AxisConfig = Field(
        default_factory=lambda: AxisConfig(
            channel=1, min_deg=-26, max_deg=26, max_speed_dps=120, max_accel_dps2=500
        )
    )

    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    idle: IdleMotion = Field(default_factory=IdleMotion)

    # Cutting drive when the head has been still briefly is what stops a
    # servo humming on your desk all evening. It is the single biggest
    # difference between a robot you keep out and one you put away.
    idle_torque_off_s: float = Field(1.2, ge=0, le=60, description="Release servos after this long at rest; 0 keeps them powered")
    update_hz: int = Field(60, ge=10, le=200)


# ---------------------------------------------------------------------------
# vision
# ---------------------------------------------------------------------------


class VisionConfig(_Base):
    enabled: bool = True
    width: int = Field(1280, ge=160, le=4608)
    height: int = Field(720, ge=120, le=2592)
    fps: int = Field(15, ge=1, le=60)
    rotation: Literal[0, 90, 180, 270] = 0
    hflip: bool = False

    # Field of view of the fitted lens. The tracker converts a face's offset
    # from image centre into degrees with these, so a wrong value makes Rocky
    # consistently under- or over-shoot when it turns to look at you.
    h_fov_deg: float = Field(102.0, ge=20, le=180, description="Horizontal FOV; 102 for Camera Module 3 Wide")
    v_fov_deg: float = Field(67.0, ge=15, le=170, description="Vertical FOV")

    detector: Literal["mediapipe", "haar", "none"] = "mediapipe"
    detect_hz: float = Field(8.0, ge=0.5, le=30)
    min_confidence: float = Field(0.55, ge=0.05, le=0.99)

    scene_interval_s: float = Field(45.0, ge=5, le=3600, description="How often to ask the model what it sees")
    scene_on_change_only: bool = Field(True, description="Only describe the scene when the frame changes materially")
    change_threshold: float = Field(0.14, ge=0.01, le=1.0)

    stream_quality: int = Field(70, ge=20, le=95, description="Dashboard MJPEG quality")
    stream_fps: int = Field(10, ge=1, le=30)


# ---------------------------------------------------------------------------
# audio
# ---------------------------------------------------------------------------


class WakeConfig(_Base):
    enabled: bool = True
    backend: Literal["openwakeword", "energy", "none"] = "openwakeword"
    model: str = "hey_rocky"
    threshold: float = Field(0.55, ge=0.05, le=0.99)
    cooldown_s: float = Field(1.5, ge=0, le=20)
    # With this on, Rocky answers follow-ups without the wake word for a while.
    open_mic_after_reply_s: float = Field(8.0, ge=0, le=120)


class SttConfig(_Base):
    backend: Literal["faster-whisper", "none"] = "faster-whisper"
    model: str = "base.en"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    language: str = "en"
    max_utterance_s: float = Field(15.0, ge=2, le=120)
    silence_s: float = Field(0.75, ge=0.2, le=5, description="Silence that ends an utterance")
    vad_threshold: float = Field(0.012, ge=0.0001, le=0.5, description="RMS gate for the fallback VAD")


class TtsConfig(_Base):
    backend: Literal["piper", "espeak", "none"] = "piper"
    voice: str = "en_GB-alan-medium"
    # Rocky is not human and should not sound like one. Pitch and rate shifts
    # plus the chirps below are what make the voice read as Rocky rather than
    # as a generic assistant.
    pitch_shift: float = Field(-1.5, ge=-12, le=12, description="Semitones")
    rate: float = Field(0.97, ge=0.5, le=2.0)
    volume: float = Field(0.85, ge=0, le=1)


class ChirpConfig(_Base):
    """Rocky's musical punctuation.

    Rocky thinks in chords, and speech is a second language. Every utterance is
    topped and tailed with a short motif, and the emotional ones stand alone.
    """

    enabled: bool = True
    volume: float = Field(0.45, ge=0, le=1)
    base_hz: float = Field(196.0, ge=60, le=800, description="Root note; low G by default")
    harmonics: int = Field(3, ge=1, le=6)
    duration_s: float = Field(0.34, ge=0.05, le=2.0)
    before_speech: bool = True
    after_speech: bool = False


class AudioConfig(_Base):
    enabled: bool = True
    input_device: str = Field("", description="ALSA/PortAudio name fragment; empty means default")
    output_device: str = ""
    sample_rate: int = Field(16000, ge=8000, le=48000)
    frame_ms: int = Field(30, ge=10, le=60)
    input_gain: float = Field(1.0, ge=0.05, le=8.0)

    wake: WakeConfig = Field(default_factory=WakeConfig)
    stt: SttConfig = Field(default_factory=SttConfig)
    tts: TtsConfig = Field(default_factory=TtsConfig)
    chirps: ChirpConfig = Field(default_factory=ChirpConfig)


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------


class WebConfig(_Base):
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = Field(8080, ge=1, le=65535)
    telemetry_hz: float = Field(4.0, ge=0.2, le=30)


class HardwareConfig(_Base):
    """Which backends to use.

    ``auto`` probes for the real thing and falls back to simulation, which is
    what lets the same code run on the Pi and on a laptop.
    """

    servos: Literal["auto", "pca9685", "sim"] = "auto"
    camera: Literal["auto", "picamera2", "sim"] = "auto"
    display: Literal["auto", "pygame", "sim"] = "auto"
    audio: Literal["auto", "sounddevice", "sim"] = "auto"


class Config(_Base):
    identity: Identity = Field(default_factory=Identity)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    face: FaceConfig = Field(default_factory=FaceConfig)
    motion: MotionConfig = Field(default_factory=MotionConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    hardware: HardwareConfig = Field(default_factory=HardwareConfig)

    log_level: str = "INFO"
    state_dir: str = "var"

    # -- loading and saving -------------------------------------------------

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        data: dict[str, Any] = {}
        if path.exists():
            data = tomllib.loads(path.read_text())
        cfg = cls.model_validate(data)
        cfg._apply_env()
        return cfg

    def _apply_env(self) -> None:
        """ROCKY_MOTION__PAN__MAX_DEG=80 overrides motion.pan.max_deg.

        Double underscore separates levels so single-underscore field names
        survive intact.
        """
        for key, raw in os.environ.items():
            if not key.startswith("ROCKY_") or key in ("ROCKY_CONFIG",):
                continue
            path = key[len("ROCKY_") :].lower().replace("__", ".")
            if "." not in path and not hasattr(self, path):
                continue
            try:
                self.set_path(path, _coerce(raw))
            except (AttributeError, ValueError, TypeError):
                continue

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_to_toml(self.model_dump(mode="json")))
        return path

    # -- dotted-path access, used by the dashboard --------------------------

    def get_path(self, path: str) -> Any:
        node: Any = self
        for part in path.split("."):
            node = getattr(node, part)
        return node

    def set_path(self, path: str, value: Any) -> Any:
        """Assign one field. Validation runs on assignment, so an out-of-range
        slider raises instead of reaching a servo."""
        parts = path.split(".")
        node: Any = self
        for part in parts[:-1]:
            node = getattr(node, part)
        leaf = parts[-1]
        if not isinstance(node, BaseModel) or leaf not in type(node).model_fields:
            raise AttributeError(f"unknown setting: {path}")
        field = type(node).model_fields[leaf]
        if field.annotation is int and isinstance(value, float) and value.is_integer():
            value = int(value)
        setattr(node, leaf, value)
        return getattr(node, leaf)

    def flatten(self) -> dict[str, Any]:
        """Every scalar as ``dotted.path -> value``, for the dashboard."""
        out: dict[str, Any] = {}

        def walk(model: BaseModel, prefix: str) -> None:
            for name in type(model).model_fields:
                value = getattr(model, name)
                key = f"{prefix}{name}"
                if isinstance(value, BaseModel):
                    walk(value, f"{key}.")
                else:
                    out[key] = value

        walk(self, "")
        return out

    def schema_for_ui(self) -> dict[str, dict[str, Any]]:
        """Bounds, types and help text per dotted path, so the dashboard can
        render the right control without hardcoding a single field name."""
        out: dict[str, dict[str, Any]] = {}

        def walk(model: BaseModel, prefix: str) -> None:
            for name, field in type(model).model_fields.items():
                value = getattr(model, name)
                key = f"{prefix}{name}"
                if isinstance(value, BaseModel):
                    walk(value, f"{key}.")
                    continue
                meta: dict[str, Any] = {"type": type(value).__name__}
                if field.description:
                    meta["help"] = field.description
                for item in field.metadata:
                    for attr, out_key in (
                        ("ge", "min"), ("gt", "min_exclusive"),
                        ("le", "max"), ("lt", "max_exclusive"),
                    ):
                        if hasattr(item, attr):
                            meta[out_key] = getattr(item, attr)
                choices = _literal_choices(field.annotation)
                if choices:
                    meta["choices"] = choices
                out[key] = meta

        walk(self, "")
        return out


def _literal_choices(annotation: Any) -> list[Any] | None:
    import typing

    if typing.get_origin(annotation) is Literal:
        return list(typing.get_args(annotation))
    return None


def _coerce(raw: str) -> Any:
    low = raw.strip().lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _to_toml(data: dict[str, Any], prefix: str = "") -> str:
    """Minimal TOML writer - the config is scalars and nested tables only, so
    pulling in a dependency to emit it is not worth it."""
    scalars, tables = [], []
    for key, value in data.items():
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            scalars.append((key, value))

    lines = []
    for key, value in scalars:
        lines.append(f"{key} = {_toml_value(value)}")
    body = "\n".join(lines)
    if body:
        body += "\n"

    for key, value in tables:
        name = f"{prefix}{key}"
        body += f"\n[{name}]\n" + _to_toml(value, prefix=f"{name}.")
    return body


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
