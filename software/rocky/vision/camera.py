"""Camera backends."""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from rocky.config import VisionConfig
from rocky.vision.imaging import encode_png, luma_signature

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    data: bytes
    mime: str
    width: int
    height: int
    # Tiny greyscale thumbnail used for change detection. Comparing encoded
    # bytes does not work; see rocky.vision.imaging.luma_signature.
    signature: bytes = b""
    # Ground truth, only ever populated by the simulator. The real camera
    # leaves it None and the detector has to do actual work.
    truth: tuple[float, float, float, float] | None = None


class CameraBackend(ABC):
    @abstractmethod
    def capture(self) -> CapturedFrame | None: ...

    def close(self) -> None: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class Picamera2Backend(CameraBackend):
    """Raspberry Pi Camera Module 3 via libcamera."""

    def __init__(self, cfg: VisionConfig) -> None:
        from picamera2 import Picamera2  # noqa: PLC0415 - optional hardware dependency

        self.cfg = cfg
        self._cam = Picamera2()
        # A second low-resolution stream costs almost nothing on the ISP and
        # gives us raw pixels for change detection without decoding the JPEG.
        config = self._cam.create_video_configuration(
            main={"size": (cfg.width, cfg.height), "format": "RGB888"},
            lores={"size": (128, 96), "format": "RGB888"},
        )
        transform_needed = cfg.rotation or cfg.hflip
        if transform_needed:
            from libcamera import Transform  # noqa: PLC0415

            config["transform"] = Transform(
                hflip=1 if cfg.hflip else 0,
                vflip=1 if cfg.rotation == 180 else 0,
            )
        self._cam.configure(config)
        self._cam.start()
        time.sleep(0.4)  # let auto-exposure settle before the first frame
        log.info("picamera2 started at %dx%d", cfg.width, cfg.height)

    def capture(self) -> CapturedFrame | None:
        import io  # noqa: PLC0415

        buffer = io.BytesIO()
        self._cam.capture_file(buffer, format="jpeg")
        signature = b""
        try:
            lores = self._cam.capture_array("lores")
            signature = luma_signature(lores.tobytes(), lores.shape[1], lores.shape[0])
        except Exception:
            log.debug("lores capture unavailable; change detection disabled", exc_info=True)
        return CapturedFrame(
            data=buffer.getvalue(), mime="image/jpeg",
            width=self.cfg.width, height=self.cfg.height, signature=signature,
        )

    def close(self) -> None:
        try:
            self._cam.stop()
            self._cam.close()
        except Exception:  # pragma: no cover
            log.debug("camera teardown was not clean", exc_info=True)


class SimCamera(CameraBackend):
    """A synthetic room with someone moving about in it.

    This is not a placeholder image, and it is not open-loop. The subject sits
    at a real bearing in the room and drifts slowly; where it lands in the
    frame depends on where the head is currently pointing, which is fed back
    from the motion service. Turn the head and the subject moves across the
    frame exactly as it would through a real lens, so face tracking genuinely
    converges here - and a regression that makes Rocky overshoot or hunt shows
    up in the simulator instead of on your desk.

    If the subject falls outside the lens's field of view it is simply not in
    the picture, which is what makes the idle scanning behaviour meaningful.
    """

    def __init__(self, cfg: VisionConfig, *, downscale: int = 8) -> None:
        self.cfg = cfg
        self.w = max(32, cfg.width // downscale)
        self.h = max(24, cfg.height // downscale)
        self._t0 = time.time()
        self._seq = 0
        self._head = (0.0, 0.0)      # pan, tilt in degrees
        self.drift = True            # off makes the subject hold still, for tests

    def set_head_angles(self, pan: float, tilt: float) -> None:
        """Told by the vision service from the motion service's pose."""
        self._head = (pan, tilt)

    def subject_bearing(self, t: float | None = None) -> tuple[float, float, float]:
        """Where the subject actually is in the room: azimuth, elevation,
        distance-driven angular size, all in degrees."""
        if not self.drift:
            return 18.0, -4.0, 22.0
        t = (time.time() if t is None else t) - self._t0
        az = 26.0 * math.sin(t * 0.17)
        el = -4.0 + 6.0 * math.sin(t * 0.11 + 1.1)
        size = 22.0 + 4.0 * math.sin(t * 0.09 + 0.4)
        return az, el, size

    def subject_position(self, t: float | None = None) -> tuple[float, float, float, float] | None:
        """Where the subject appears in frame, or None if it is out of view."""
        az, el, ang_size = self.subject_bearing(t)
        pan, tilt = self._head
        cx = 0.5 + (az - pan) / self.cfg.h_fov_deg
        cy = 0.5 - (el - tilt) / self.cfg.v_fov_deg
        bw = ang_size / self.cfg.h_fov_deg
        bh = bw * 1.25
        if not (-bw < cx < 1 + bw) or not (-bh < cy < 1 + bh):
            return None
        return cx, cy, bw, bh

    def capture(self) -> CapturedFrame | None:
        self._seq += 1
        subject = self.subject_position()
        w, h, = self.w, self.h
        px = bytearray(w * h * 3)

        for y in range(h):
            v = y / h
            # A plausible room: warm wall, darker desk in the lower third.
            if v > 0.72:
                base = (46, 40, 38)
            else:
                g = int(28 + 26 * (1.0 - v))
                base = (g + 8, g + 4, g)
            row = y * w * 3
            for x in range(w):
                i = row + x * 3
                px[i], px[i + 1], px[i + 2] = base

        if subject is None:
            return CapturedFrame(
                data=encode_png(bytes(px), w, h), mime="image/png",
                width=w, height=h,
                signature=luma_signature(bytes(px), w, h), truth=None,
            )

        cx, cy, bw, bh = subject
        # subject: a head-ish ellipse with a torso below it
        hx, hy = cx * w, cy * h
        rx, ry = bw * w * 0.5, bh * h * 0.5
        for y in range(max(0, int(hy - ry)), min(h, int(hy + ry) + 1)):
            for x in range(max(0, int(hx - rx)), min(w, int(hx + rx) + 1)):
                nx = (x - hx) / max(1e-6, rx)
                ny = (y - hy) / max(1e-6, ry)
                if nx * nx + ny * ny <= 1.0:
                    i = (y * w + x) * 3
                    shade = 1.0 - 0.25 * ny
                    px[i] = min(255, int(214 * shade))
                    px[i + 1] = min(255, int(176 * shade))
                    px[i + 2] = min(255, int(150 * shade))

        return CapturedFrame(
            data=encode_png(bytes(px), w, h), mime="image/png",
            width=w, height=h,
            signature=luma_signature(bytes(px), w, h),
            truth=(cx, cy, bw, bh),
        )


def make_camera(preference: str, cfg: VisionConfig) -> CameraBackend:
    if preference == "sim":
        return SimCamera(cfg)
    try:
        return Picamera2Backend(cfg)
    except Exception as exc:
        if preference == "picamera2":
            raise
        log.info("No camera (%s); using the simulated room", exc)
        return SimCamera(cfg)
