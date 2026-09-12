"""Finding people in a frame."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from rocky.config import VisionConfig
from rocky.core.events import Detection
from rocky.vision.camera import CapturedFrame

log = logging.getLogger(__name__)


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: CapturedFrame) -> list[Detection]: ...

    def close(self) -> None: ...

    @property
    def kind(self) -> str:
        return type(self).__name__


class NullDetector(Detector):
    def detect(self, frame: CapturedFrame) -> list[Detection]:
        return []


class SimDetector(Detector):
    """Reads the simulator's ground truth.

    Honest about what it is: it does no image processing. Its job is to let
    everything downstream of detection - tracking, gaze, the brain noticing
    someone arrived - run and be tested without a camera.
    """

    def detect(self, frame: CapturedFrame) -> list[Detection]:
        if frame.truth is None:
            return []
        cx, cy, w, h = frame.truth
        return [Detection(label="face", cx=cx, cy=cy, w=w, h=h, score=0.95)]


class MediaPipeDetector(Detector):
    """MediaPipe face detection - fast enough for the Pi 5's CPU."""

    def __init__(self, cfg: VisionConfig) -> None:
        import cv2  # noqa: PLC0415
        import mediapipe as mp  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        self.cv2, self.np = cv2, np
        self.cfg = cfg
        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1,  # 1 is the full-range model: better past 2m
            min_detection_confidence=cfg.min_confidence,
        )

    def detect(self, frame: CapturedFrame) -> list[Detection]:
        buf = self.np.frombuffer(frame.data, dtype=self.np.uint8)
        image = self.cv2.imdecode(buf, self.cv2.IMREAD_COLOR)
        if image is None:
            return []
        rgb = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        if not result.detections:
            return []

        out: list[Detection] = []
        for det in result.detections:
            box = det.location_data.relative_bounding_box
            score = float(det.score[0]) if det.score else 0.0
            if score < self.cfg.min_confidence:
                continue
            out.append(
                Detection(
                    label="face",
                    cx=float(box.xmin + box.width / 2),
                    cy=float(box.ymin + box.height / 2),
                    w=float(box.width),
                    h=float(box.height),
                    score=score,
                )
            )
        return out

    def close(self) -> None:
        try:
            self._detector.close()
        except Exception:  # pragma: no cover
            pass


class HaarDetector(Detector):
    """OpenCV cascade. Cruder than MediaPipe but has no extra dependency."""

    def __init__(self, cfg: VisionConfig) -> None:
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        self.cv2, self.np = cv2, np
        self.cfg = cfg
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(path)
        if self._cascade.empty():
            raise RuntimeError(f"could not load cascade at {path}")

    def detect(self, frame: CapturedFrame) -> list[Detection]:
        buf = self.np.frombuffer(frame.data, dtype=self.np.uint8)
        image = self.cv2.imdecode(buf, self.cv2.IMREAD_GRAYSCALE)
        if image is None:
            return []
        h, w = image.shape[:2]
        found = self._cascade.detectMultiScale(image, 1.15, 5, minSize=(int(w * 0.06),) * 2)
        return [
            Detection(
                label="face",
                cx=(x + bw / 2) / w, cy=(y + bh / 2) / h,
                w=bw / w, h=bh / h, score=0.8,
            )
            for (x, y, bw, bh) in found
        ]


def make_detector(cfg: VisionConfig, camera_kind: str) -> Detector:
    if cfg.detector == "none":
        return NullDetector()
    if camera_kind == "SimCamera":
        return SimDetector()
    order = [cfg.detector] + [d for d in ("mediapipe", "haar") if d != cfg.detector]
    for choice in order:
        try:
            if choice == "mediapipe":
                return MediaPipeDetector(cfg)
            if choice == "haar":
                return HaarDetector(cfg)
        except Exception as exc:
            log.info("detector %s unavailable: %s", choice, exc)
    log.warning("no detector available; Rocky will not track faces")
    return NullDetector()
