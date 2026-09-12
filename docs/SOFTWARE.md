# Software

Install, calibrate, and tune.

## Install on the Pi

```bash
git clone https://github.com/JohnKessler/rocky /tmp/rocky
sudo /tmp/rocky/scripts/install.sh
```

That installs system packages, enables I²C, creates a `rocky` user with the
right groups, builds a virtualenv at `/opt/rocky/.venv`, and installs a systemd
unit. It is safe to re-run — it upgrades in place and leaves `config.toml`
alone.

Then put your API key where the service can find it:

```bash
sudo nano /etc/rocky/rocky.env     # ANTHROPIC_API_KEY=sk-ant-...
sudo systemctl start rocky
journalctl -u rocky -f
```

Without a key Rocky still watches, tracks, moves and chirps. It just does not
converse.

### Speech engines

The installer tries to install `faster-whisper`, `piper` and `openwakeword`.
They are large and occasionally fight a particular Pi image, so failure is
non-fatal: Rocky falls back to `espeak-ng` for speech out and to a
speech-triggered wake for speech in, and says so in the log.

Piper needs a voice model on disk. Download one and drop it in
`/opt/rocky/var/voices/`:

```bash
cd /opt/rocky/var/voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json
```

Then set `audio.tts.voice = "en_GB-alan-medium"`.

For the wake word, openWakeWord ships several pretrained models but not
"hey rocky". Either train one (their docs cover it), pick an existing model and
set `audio.wake.model`, or set `audio.wake.backend = "energy"` and let any
sustained speech wake Rocky. Energy wake is pleasant if you work alone and
useless in a room with a television.

## Commands

```bash
rocky run                  # the normal one
rocky run --no-web         # without the dashboard
rocky --sim run            # everything simulated, works anywhere
rocky check                # probe the hardware and report what is real
rocky calibrate pan        # interactive centring, writes the trim back
rocky calibrate tilt
rocky ask "what can you see"
rocky say "Good, good, good."
rocky config               # print the effective configuration
```

`rocky check` is the one to run first on a fresh build. It reports every backend
as `ok` (real hardware) or `sim` (fell back), which turns "why is nothing
happening" into a list.

## Configuration

Precedence, lowest to highest:

```
defaults in config.py  →  config.toml  →  ROCKY_* environment  →  dashboard edits
```

Dashboard edits apply immediately and are lost on restart unless you press
**Save**, which writes them back to `config.toml`. That is deliberate: you can
experiment freely and a bad idea disappears when you restart.

Environment overrides use a double underscore between levels:

```bash
ROCKY_MOTION__PAN__MAX_SPEED_DPS=90
ROCKY_BRAIN__EFFORT=medium
ROCKY_LOG_LEVEL=DEBUG
```

Every setting is bounded, and the bounds are enforced wherever the value enters
— including from the dashboard, which is why a slider cannot drive a servo past
its limits.

## Calibration

### Servo centres

```bash
rocky calibrate pan
```

`a`/`d` nudge by a degree, `A`/`D` by five, `0` commands zero, `s` saves and
quits. It writes `motion.<axis>.centre_trim_deg`.

Do this rather than trying to get the horn splines mechanically perfect. A
standard servo spline is 1.5° per tooth, so mechanical alignment can only ever
get you within three quarters of a degree; the trim gets you exact.

### Camera field of view

`vision.h_fov_deg` and `v_fov_deg` must match your lens. They are what convert
"the face is 30% right of centre" into "turn 15 degrees", so a wrong value makes
Rocky consistently under- or over-shoot when it turns to look at you.

- Camera Module 3 **Wide**: 102 × 67 (the default)
- Camera Module 3 standard: 66 × 41

To check empirically: put your face at the edge of frame, let Rocky track it,
and watch whether the head lands short or long. Short means the FOV is set too
narrow.

### Tracking

If Rocky overshoots and corrects back, lower `motion.tracking.gain` — try 0.4.
If it creeps continuously while you sit still, raise
`motion.tracking.deadband`. If it feels twitchy, raise `damping`.

The **Motion** tab shows the head's position and its target on one map, which
makes overshoot and hunting obvious.

## Tuning Rocky's personality

The **Personality** tab has seven dials. They are not decoration — each one is
quoted into the prompt and read by the face and motion services, so a change
takes effect within a second or two.

| Dial | What it changes |
|------|-----------------|
| `curiosity` | How often Rocky asks about things, and how much it looks around when idle |
| `chattiness` | Whether Rocky speaks unprompted, including whether it greets you |
| `playfulness` | Teasing, jokes, sillier chords |
| `warmth` | How openly it says it likes you |
| `formality` | Sentence register. Low is the default; Rocky's speech is plain by design |
| `energy` | Gesture amplitude, blink rate, speech pace |
| `focus` | How long it stays on a subject, and how much its eyes wander |

Rocky can turn these itself. Say "be quieter" and it will reach for its
`adjust_self` tool, which is the same code path as the slider.

To change the character more deeply, edit `software/rocky/brain/persona.py`.
It is assembled rather than written flat so you can read exactly what each dial
contributed.

## Cost

Rocky makes one API request per conversational turn, plus one small request
whenever it describes the scene.

Levers, in the order worth reaching for:

1. `vision.scene_interval_s` — how often Rocky looks at the room. The default
   of 45 s with `scene_on_change_only` is already conservative; raise it or set
   `brain.scene_in_context = false` to stop entirely.
2. `brain.effort` — `low` by default, because a spoken companion answers in a
   sentence or two and the gap between you stopping and Rocky starting matters
   more than depth. Raise it if you start asking harder questions.
3. `brain.history_turns` — how much conversation is resent each turn.
4. `brain.max_tokens` — a hard ceiling on the reply.

The system prompt and tool list are identical every turn and are cached, so most
of the per-turn input cost disappears after the first request. The **Personality**
tab shows requests, tokens and cache hits; if `cached` stays at zero across
several turns, something is varying in the prefix.

## Running it your own way

`rocky run` starts everything. If you want a subset, `RockyApp` takes a config
and starts whichever services you leave enabled:

```python
from rocky.app import RockyApp
from rocky.config import Config

cfg = Config.load()
cfg.vision.enabled = False      # no camera
cfg.motion.enabled = False      # no servos

app = RockyApp(cfg)
await app.start()
await app.say("Good, good, good.")
```

The web app can own the robot's lifecycle if you would rather embed it:

```python
from rocky.web.app import create_app
api = create_app(RockyApp(cfg), manage_lifecycle=True)
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

252 tests, about forty seconds, all against the simulated backends — so they
pass on a laptop, in CI, and on the robot. They are worth reading if you plan to
change anything: several assert on behaviour that is easy to break silently,
like the motion profile never overshooting, the eyelid never covering the pupil,
and the microphone being shut while Rocky talks.
