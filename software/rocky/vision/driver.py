"""The vision service: capture, detect, and notice change.

Deliberately does not talk to the model. Everything that costs API calls lives
in ``rocky.brain``, so there is exactly one place in the robot that spends
money and one place to look when the bill is wrong. Vision's job is to publish
frames, publish detections, and say when the room changed enough to be worth a
second look.
"""

from __future__ import annotations

import time
from typing import Any

from rocky.core import events as ev
from rocky.core.service import Service
from rocky.vision.camera import CameraBackend, CapturedFrame, make_camera
from rocky.vision.detector import Detector, make_detector
from rocky.vision.imaging import frame_difference


class VisionService(Service):
    """Runs the camera and the face detector on independent schedules."""

    name = "vision"

    def __init__(self, bus, config) -> None:
        super().__init__(bus, config)
        self.camera: CameraBackend | None = None
        self.detector: Detector | None = None
        self._seq = 0
        self._last_detect = 0.0
        self._last_stream = 0.0
        self._latest: CapturedFrame | None = None
        self._reference: bytes = b""
        self._change = 0.0
        self._last_faces: tuple[ev.Detection, ...] = ()
        self._people_present = False
        self._detect_ms = 0.0

    async def setup(self) -> None:
        cfg = self.config.vision
        self.camera = make_camera(self.config.hardware.camera, cfg)
        self.detector = make_detector(cfg, self.camera.kind)
        self.log.info("camera=%s detector=%s", self.camera.kind, self.detector.kind)

    async def teardown(self) -> None:
        if self.detector:
            self.detector.close()
            self.detector = None
        if self.camera:
            self.camera.close()
            self.camera = None

    async def run(self) -> None:
        cfg = self.config.vision
        while True:
            period = 1.0 / max(1, cfg.fps)
            if cfg.enabled:
                try:
                    self._tick()
                except Exception:
                    self.log.exception("vision tick failed")
            if not await self.sleep(period):
                return

    def _tick(self) -> None:
        assert self.camera is not None
        cfg = self.config.vision
        now = time.time()

        frame = self.camera.capture()
        if frame is None:
            return
        self._seq += 1
        self._latest = frame

        # How different is this from the last frame we considered notable?
        self._change = frame_difference(self._reference, frame.signature)
        if not self._reference or self._change > cfg.change_threshold:
            self._reference = frame.signature
            if self._seq > 3:  # ignore the settling frames at startup
                self.bus.publish(ev.MOTION_DETECTED, {"change": round(self._change, 3)})

        if now - self._last_stream >= 1.0 / max(1, cfg.stream_fps):
            self._last_stream = now
            self.bus.publish(
                ev.FRAME,
                ev.Frame(
                    data=frame.data, mime=frame.mime,
                    width=frame.width, height=frame.height, seq=self._seq,
                ),
            )

        if self.detector and now - self._last_detect >= 1.0 / max(0.1, cfg.detect_hz):
            self._last_detect = now
            started = time.perf_counter()
            found = tuple(self.detector.detect(frame))
            self._detect_ms = (time.perf_counter() - started) * 1000.0
            self._last_faces = found
            self.bus.publish(ev.FACES, ev.Faces(items=found, seq=self._seq))

            # Somebody arriving or leaving is worth telling the brain about,
            # because it is the cue for Rocky to greet you or go quiet.
            present = bool(found)
            if present != self._people_present:
                self._people_present = present
                self.bus.publish(
                    ev.SCENE,
                    ev.Scene(
                        summary="Someone came into view" if present else "The view is empty now",
                        tags=("presence",),
                        notable_change=True,
                    ),
                )

    # -- accessors used by the brain and the dashboard ----------------------

    def latest_frame(self) -> CapturedFrame | None:
        return self._latest

    def snapshot(self) -> dict[str, Any]:
        return {
            "camera": self.camera.kind if self.camera else "none",
            "detector": self.detector.kind if self.detector else "none",
            "frames": self._seq,
            "faces": len(self._last_faces),
            "change": round(self._change, 3),
            "detect_ms": round(self._detect_ms, 1),
            "present": self._people_present,
        }
