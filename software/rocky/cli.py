"""Command line entry points."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import signal
import sys
from typing import Any

from rocky import __version__
from rocky.config import Config

log = logging.getLogger("rocky.cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rocky", description="Rocky - a compact desk companion"
    )
    parser.add_argument("--config", help="path to config.toml")
    parser.add_argument("--sim", action="store_true",
                        help="force every backend into simulation")
    parser.add_argument("--version", action="version", version=f"rocky {__version__}")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="run Rocky (this is the normal one)")
    run.add_argument("--no-web", action="store_true", help="skip the dashboard")
    run.add_argument("--port", type=int, help="dashboard port")

    sub.add_parser("check", help="probe the hardware and report what was found")
    sub.add_parser("config", help="print the effective configuration")

    say = sub.add_parser("say", help="make Rocky speak some text and exit")
    say.add_argument("text", nargs="+")

    ask = sub.add_parser("ask", help="ask Rocky something and print the reply")
    ask.add_argument("text", nargs="+")

    cal = sub.add_parser("calibrate", help="interactive servo centring")
    cal.add_argument("axis", choices=["pan", "tilt"], nargs="?", default="pan")

    args = parser.parse_args(argv)
    cfg = Config.load(args.config)
    if args.sim:
        for field in ("servos", "camera", "display", "audio"):
            setattr(cfg.hardware, field, "sim")

    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)-14s %(message)s",
        datefmt="%H:%M:%S",
    )

    command = args.command or "run"
    handler = {
        "run": lambda: _run(cfg, args),
        "check": lambda: _check(cfg),
        "config": lambda: _print_config(cfg),
        "say": lambda: _one_shot(cfg, " ".join(args.text), speak=True),
        "ask": lambda: _one_shot(cfg, " ".join(args.text), speak=False),
        "calibrate": lambda: _calibrate(cfg, args.axis),
    }[command]

    try:
        return asyncio.run(handler())
    except KeyboardInterrupt:
        print()
        return 0


# ---------------------------------------------------------------------------


async def _run(cfg: Config, args: Any) -> int:
    from rocky.app import RockyApp

    if args.port:
        cfg.web.port = args.port

    app = RockyApp(cfg)
    await app.start()

    server = None
    if cfg.web.enabled and not args.no_web:
        server = await _start_web(app)
        print(f"\n  Dashboard: http://{_display_host(cfg.web.host)}:{cfg.web.port}\n")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    await stop.wait()
    log.info("shutting down")
    if server:
        server.should_exit = True
        await asyncio.sleep(0.3)
    await app.stop()
    return 0


async def _start_web(app: Any):
    import uvicorn

    from rocky.web.app import create_app

    config = uvicorn.Config(
        create_app(app),
        host=app.config.web.host,
        port=app.config.web.port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve(), name="rocky-web")
    for _ in range(100):
        if getattr(server, "started", False):
            break
        await asyncio.sleep(0.05)
    return server


async def _check(cfg: Config) -> int:
    """Probe every backend and say what is actually present.

    Run this first on a fresh build - it answers "is my hardware wired up"
    without needing the rest of the robot to work.
    """
    from rocky.audio.devices import make_audio_io
    from rocky.audio.stt import make_stt
    from rocky.audio.tts import make_tts
    from rocky.face.renderer import make_renderer
    from rocky.motion.servo import make_servo_backend
    from rocky.vision.camera import make_camera
    from rocky.vision.detector import make_detector

    print(f"rocky {__version__}\n")
    rows: list[tuple[str, str, bool]] = []

    def probe(label: str, factory, real_prefixes: tuple[str, ...]) -> Any:
        try:
            obj = factory()
            kind = obj.kind if hasattr(obj, "kind") else type(obj).__name__
            rows.append((label, kind, any(kind.startswith(p) for p in real_prefixes)))
            return obj
        except Exception as exc:
            rows.append((label, f"failed: {exc}", False))
            return None

    servos = probe(
        "servos",
        lambda: make_servo_backend(
            cfg.hardware.servos, cfg.motion.i2c_address, cfg.motion.pwm_frequency
        ),
        ("PCA9685",),
    )
    camera = probe(
        "camera", lambda: make_camera(cfg.hardware.camera, cfg.vision), ("Picamera2",)
    )
    if camera:
        probe(
            "detector",
            lambda: make_detector(cfg.vision, camera.kind),
            ("MediaPipe", "Haar"),
        )
    probe("display", lambda: make_renderer(cfg.hardware.display, cfg.face), ("Pygame",))
    probe(
        "audio io",
        lambda: make_audio_io(
            cfg.hardware.audio, cfg.audio.sample_rate, 480,
            cfg.audio.input_device, cfg.audio.output_device,
        ),
        ("SoundDevice",),
    )
    probe("speech in", lambda: make_stt(cfg.audio.stt), ("FasterWhisper",))
    probe("speech out", lambda: make_tts(cfg.audio.tts), ("Piper", "Espeak"))

    try:
        import os

        import anthropic  # noqa: F401
        has_key = bool(
            os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )
        found = "found" if has_key else "NOT found"
        rows.append(("brain", f"anthropic sdk, credentials {found}", has_key))
    except Exception as exc:
        rows.append(("brain", f"failed: {exc}", False))

    width = max(len(r[0]) for r in rows)
    for label, detail, real in rows:
        mark = "ok  " if real else "sim "
        print(f"  [{mark}] {label.ljust(width)}  {detail}")

    simulated = [r[0] for r in rows if not r[2]]
    print()
    if simulated:
        print(f"  Running simulated: {', '.join(simulated)}")
        print("  That is fine on a laptop. On the robot, check wiring and drivers.")
    else:
        print("  Everything is real. Rocky is fully assembled.")

    if servos:
        servos.close()
    if camera:
        camera.close()
    return 0


async def _print_config(cfg: Config) -> int:
    print(json.dumps(cfg.model_dump(mode="json"), indent=2))
    return 0


async def _one_shot(cfg: Config, text: str, *, speak: bool) -> int:
    from rocky.app import RockyApp

    app = RockyApp(cfg)
    await app.start()
    try:
        if speak:
            await app.say(text)
            await asyncio.sleep(0.2)
        else:
            reply = await app.ask(text)
            print(reply or "(Rocky answered with a chord and a look.)")
            await asyncio.sleep(0.5)
    finally:
        await app.stop()
    return 0


async def _calibrate(cfg: Config, axis: str) -> int:
    """Nudge one axis and write the trim back.

    Print the horn on its splines wherever it lands, then use this to teach
    Rocky where straight ahead actually is - that is far easier than trying to
    get the spline alignment right mechanically.
    """
    from rocky.motion.kinematics import angle_to_pulse_us
    from rocky.motion.servo import make_servo_backend

    axis_cfg = getattr(cfg.motion, axis)
    backend = make_servo_backend(
        cfg.hardware.servos, cfg.motion.i2c_address, cfg.motion.pwm_frequency
    )
    print(f"\nCalibrating {axis} on channel {axis_cfg.channel}.")
    print("  a / d  nudge by 1 degree      A / D  nudge by 5")
    print("  0      command zero            s     save trim and quit")
    print("  q      quit without saving\n")

    trim = axis_cfg.centre_trim_deg

    def drive() -> None:
        backend.set_pulse(
            axis_cfg.channel,
            angle_to_pulse_us(
                0.0,
                pulse_min_us=axis_cfg.pulse_min_us, pulse_max_us=axis_cfg.pulse_max_us,
                range_deg=axis_cfg.range_deg, trim_deg=trim, invert=axis_cfg.invert,
            ),
        )
        print(f"\r  trim {trim:+6.1f}°   ", end="", flush=True)

    drive()
    try:
        while True:
            key = sys.stdin.read(1)
            if not key or key == "q":
                break
            if key == "a":
                trim -= 1
            elif key == "d":
                trim += 1
            elif key == "A":
                trim -= 5
            elif key == "D":
                trim += 5
            elif key == "0":
                trim = 0.0
            elif key == "s":
                cfg.set_path(f"motion.{axis}.centre_trim_deg", trim)
                path = cfg.save()
                print(f"\n  saved {axis} trim {trim:+.1f}° to {path}")
                break
            else:
                continue
            drive()
    finally:
        backend.release(axis_cfg.channel)
        backend.close()
    print()
    return 0


def _display_host(host: str) -> str:
    return "localhost" if host in ("0.0.0.0", "::", "") else host


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
