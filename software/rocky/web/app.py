"""The dashboard's HTTP and websocket API.

Every control here goes through the same bus events the brain uses, so the
dashboard is not a special case wired into the internals - pressing "nod" in
the browser is indistinguishable, downstream, from Rocky deciding to nod.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rocky.audio.chirps import MOTIF_NAMES, MOTIFS
from rocky.core import events as ev
from rocky.face.expressions import EXPRESSION_NAMES
from rocky.motion.gestures import GESTURES

log = logging.getLogger("rocky.web")


def _managed_lifespan(rocky: Any):
    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        await rocky.start()
        try:
            yield
        finally:
            await rocky.stop()

    return lifespan

STATIC_DIR = Path(__file__).parent / "static"


# --- request bodies ---------------------------------------------------------


class SettingPatch(BaseModel):
    path: str
    value: Any


class TextBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ExpressionBody(BaseModel):
    name: str
    intensity: float = Field(1.0, ge=0.05, le=1.0)
    hold: float = Field(0.0, ge=0, le=300)


class GestureBody(BaseModel):
    name: str
    intensity: float = Field(1.0, ge=0.1, le=1.5)


class JogBody(BaseModel):
    pan: float | None = None
    tilt: float | None = None


class ModeBody(BaseModel):
    mode: str


class MotifBody(BaseModel):
    motif: str


def create_app(rocky: Any, *, manage_lifecycle: bool = False) -> FastAPI:
    """Build the API around a :class:`rocky.app.RockyApp`.

    ``manage_lifecycle`` makes the web app start and stop the robot itself, on
    whatever event loop is serving HTTP. The CLI does not use it - there the
    robot is already running and the dashboard is optional - but it lets the
    app be embedded, and it lets the tests drive everything through one loop
    instead of trying to share services across two.
    """
    lifespan = _managed_lifespan(rocky) if manage_lifecycle else None
    app = FastAPI(title="Rocky", version="1.0.0", docs_url="/api/docs", lifespan=lifespan)

    # ---------------------------------------------------------------- pages

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        page = STATIC_DIR / "index.html"
        if not page.exists():  # pragma: no cover
            return HTMLResponse("<h1>Rocky</h1><p>Dashboard assets are missing.</p>", 500)
        return HTMLResponse(page.read_text())

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # --------------------------------------------------------------- status

    @app.get("/api/status")
    async def status() -> dict:
        return rocky.status()

    @app.get("/api/vocabulary")
    async def vocabulary() -> dict:
        """Everything Rocky can express, so the dashboard never hardcodes a
        list that then drifts out of date."""
        return {
            "expressions": list(EXPRESSION_NAMES),
            "gestures": [
                {"name": g.name, "description": g.description, "duration": g.duration}
                for g in GESTURES.values()
            ],
            "motifs": [
                {"name": m.name, "meaning": m.meaning} for m in MOTIFS.values()
            ],
            "identity": {
                "name": rocky.config.identity.name,
                "owner": rocky.config.identity.owner_name,
            },
        }

    # --------------------------------------------------------------- config

    @app.get("/api/config")
    async def get_config() -> dict:
        return {
            "values": rocky.config.flatten(),
            "schema": rocky.config.schema_for_ui(),
        }

    @app.patch("/api/config")
    async def patch_config(patch: SettingPatch) -> dict:
        try:
            applied = rocky.config.set_path(patch.path, patch.value)
        except AttributeError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (ValueError, TypeError) as exc:
            # Pydantic's message names the bound that was violated, which is
            # exactly what the person moving the slider needs to see.
            raise HTTPException(422, _first_error(exc)) from exc
        rocky.bus.publish(ev.CONFIG_CHANGED, {"path": patch.path, "value": applied})
        return {"path": patch.path, "value": applied}

    @app.post("/api/config/save")
    async def save_config() -> dict:
        path = rocky.config.save()
        return {"saved": str(path)}

    # --------------------------------------------------------------- camera

    @app.get("/api/camera/frame")
    async def camera_frame() -> Response:
        frame = rocky.vision.latest_frame()
        if frame is None:
            raise HTTPException(503, "no camera frame yet")
        return Response(content=frame.data, media_type=frame.mime)

    @app.get("/api/camera/stream")
    async def camera_stream() -> StreamingResponse:
        """Multipart stream of whatever the camera is producing."""
        boundary = "rockyframe"

        async def generate():
            last_seq = -1
            while True:
                frame = rocky.vision.latest_frame()
                if frame is not None and id(frame) != last_seq:
                    last_seq = id(frame)
                    yield (
                        f"--{boundary}\r\n"
                        f"Content-Type: {frame.mime}\r\n"
                        f"Content-Length: {len(frame.data)}\r\n\r\n"
                    ).encode() + frame.data + b"\r\n"
                await asyncio.sleep(1.0 / max(1, rocky.config.vision.stream_fps))

        return StreamingResponse(
            generate(),
            media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        )

    # --------------------------------------------------------------- speech

    @app.post("/api/say")
    async def say(body: TextBody) -> dict:
        """Speak this text verbatim - no model involved."""
        await rocky.say(body.text)
        return {"said": body.text}

    @app.post("/api/ask")
    async def ask(body: TextBody) -> dict:
        """Put text in as though Rocky had heard it. This runs the whole
        conversation path, so it is a real test of the brain, not a shortcut
        around it."""
        reply = await rocky.ask(body.text)
        return {"asked": body.text, "reply": reply}

    @app.post("/api/chirp")
    async def chirp(body: MotifBody) -> dict:
        if body.motif not in MOTIF_NAMES:
            raise HTTPException(404, f"no motif called {body.motif!r}")
        rocky.bus.publish(ev.CHIRP, ev.Chirp(body.motif))
        return {"motif": body.motif}

    @app.post("/api/audio/test")
    async def audio_test() -> dict:
        await rocky.audio.test_tone()
        return {"played": "test tone"}

    # ----------------------------------------------------------------- face

    @app.post("/api/expression")
    async def expression(body: ExpressionBody) -> dict:
        if body.name not in EXPRESSION_NAMES:
            raise HTTPException(404, f"no expression called {body.name!r}")
        rocky.bus.publish(ev.EXPRESSION, ev.Expression(body.name, body.intensity, body.hold))
        return {"expression": body.name}

    # --------------------------------------------------------------- motion

    @app.post("/api/gesture")
    async def gesture(body: GestureBody) -> dict:
        if body.name not in GESTURES:
            raise HTTPException(404, f"no gesture called {body.name!r}")
        rocky.bus.publish(ev.GESTURE, ev.Gesture(body.name, body.intensity))
        return {"gesture": body.name}

    @app.post("/api/motion/jog")
    async def jog(body: JogBody) -> dict:
        pan, tilt = rocky.motion.jog(body.pan, body.tilt)
        return {"pan": pan, "tilt": tilt}

    @app.post("/api/motion/mode")
    async def motion_mode(body: ModeBody) -> dict:
        if body.mode not in ("track", "manual", "idle", "off"):
            raise HTTPException(422, "mode must be track, manual, idle or off")
        rocky.bus.publish(ev.MOTION_MODE, body.mode)
        return {"mode": body.mode}

    @app.post("/api/motion/centre")
    async def centre() -> dict:
        pan, tilt = rocky.motion.jog(0.0, 0.0)
        return {"pan": pan, "tilt": tilt}

    # --------------------------------------------------------------- memory

    @app.get("/api/memory")
    async def list_memory() -> dict:
        if not rocky.brain.memory:
            return {"facts": [], "stats": {}}
        return {
            "facts": [f.as_dict() for f in rocky.brain.memory.all_facts()],
            "stats": rocky.brain.memory.stats(),
        }

    @app.post("/api/memory")
    async def add_memory(body: TextBody) -> dict:
        if not rocky.brain.memory:
            raise HTTPException(503, "memory is disabled")
        fact = rocky.brain.memory.remember(body.text)
        if fact is None:
            raise HTTPException(422, "nothing to remember")
        return fact.as_dict()

    @app.delete("/api/memory/{fact_id}")
    async def delete_memory(fact_id: int) -> dict:
        if not rocky.brain.memory:
            raise HTTPException(503, "memory is disabled")
        if not rocky.brain.memory.forget(fact_id):
            raise HTTPException(404, "no such fact")
        return {"forgotten": fact_id}

    @app.get("/api/transcript")
    async def transcript(limit: int = 40) -> dict:
        if not rocky.brain.memory:
            return {"turns": []}
        return {"turns": rocky.brain.memory.recent_turns(min(limit, 200))}

    # ------------------------------------------------------------ websocket

    @app.websocket("/ws")
    async def websocket(ws: WebSocket) -> None:
        """Live feed: telemetry, face parameters, transcript, logs.

        The face parameters are the same vector the on-device renderer draws,
        so the browser shows Rocky's actual face rather than a guess at it.
        """
        await ws.accept()
        topics = (
            ev.TELEMETRY, ev.FACE_FRAME, ev.SPEECH, ev.UTTERANCE, ev.POSE,
            ev.EXPRESSION, ev.GESTURE, ev.CHIRP, ev.TOOL_CALL, ev.BRAIN_STATE,
            ev.LISTENING, ev.SPEAKING, ev.SCENE, ev.LOG, ev.FACES, ev.CONFIG_CHANGED,
        )
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)

        async def forward(topic: str, payload: Any) -> None:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait((topic, payload))

        subs = [rocky.bus.subscribe(t, forward) for t in topics]
        try:
            await ws.send_text(json.dumps({"topic": "hello", "data": rocky.status()}))
            while True:
                topic, payload = await queue.get()
                await ws.send_text(
                    json.dumps({"topic": topic, "data": _encode(payload)}, default=str)
                )
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        finally:
            for sub in subs:
                sub.cancel()

    return app


def _encode(payload: Any) -> Any:
    """Make an event payload JSON-safe.

    Frames carry raw image bytes, which must never be inlined into a telemetry
    message; the dashboard fetches those over HTTP instead.
    """
    if payload is None or isinstance(payload, (str, int, float, bool)):
        return payload
    if is_dataclass(payload) and not isinstance(payload, type):
        data = asdict(payload)
        data.pop("data", None)
        data.pop("signature", None)
        return data
    if isinstance(payload, dict):
        return {k: _encode(v) for k, v in payload.items() if k not in ("data", "signature")}
    if isinstance(payload, (list, tuple)):
        return [_encode(v) for v in payload]
    return str(payload)


def _first_error(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            first = errors()[0]
            return f"{'.'.join(str(p) for p in first.get('loc', ()))}: {first.get('msg', exc)}"
        except Exception:
            pass
    return str(exc)
