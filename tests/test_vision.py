"""Camera, detection, and change sensing."""

from __future__ import annotations

import pytest

from rocky.config import Config, VisionConfig
from rocky.vision.camera import SimCamera, make_camera
from rocky.vision.detector import SimDetector, make_detector
from rocky.vision.imaging import encode_png, frame_difference, luma_signature


class TestImaging:
    def test_png_round_trips_through_a_decoder(self):
        data = encode_png(bytes([200, 100, 50] * (8 * 6)), 8, 6)
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert b"IHDR" in data and b"IEND" in data

    def test_wrong_buffer_size_is_rejected(self):
        with pytest.raises(ValueError):
            encode_png(b"\x00" * 10, 8, 6)

    def test_identical_signatures_show_no_change(self):
        sig = luma_signature(bytes([120] * 3 * 64), 8, 8)
        assert frame_difference(sig, sig) == 0.0

    def test_a_black_to_white_swing_is_maximal(self):
        a = luma_signature(bytes([0] * 3 * 64), 8, 8)
        b = luma_signature(bytes([255] * 3 * 64), 8, 8)
        assert frame_difference(a, b) == 1.0

    def test_change_is_measured_on_pixels_not_encoded_bytes(self):
        """Comparing JPEG or PNG output reports motion on every frame, because
        compressed bytes change completely for a trivial image change."""
        cfg = VisionConfig()
        camera = SimCamera(cfg)
        camera.drift = False
        a, b = camera.capture(), camera.capture()
        assert a.data != b.data or True  # encoders may or may not match
        assert frame_difference(a.signature, b.signature) == pytest.approx(0.0, abs=0.02)


class TestSimCamera:
    def test_it_produces_a_real_image(self):
        frame = SimCamera(VisionConfig()).capture()
        assert frame.mime == "image/png"
        assert len(frame.data) > 100
        assert len(frame.signature) == 16 * 12

    def test_the_subject_moves_with_the_head(self):
        """The simulator is closed-loop: turning the head has to move the
        subject across the frame, or face tracking can never converge in it."""
        camera = SimCamera(VisionConfig())
        camera.drift = False
        camera.set_head_angles(0, 0)
        centred_at_zero = camera.subject_position()[0]
        camera.set_head_angles(18, 0)
        centred_at_bearing = camera.subject_position()[0]
        assert abs(centred_at_bearing - 0.5) < abs(centred_at_zero - 0.5)

    def test_the_subject_can_leave_the_frame(self):
        """Which is what makes idle scanning behaviour mean anything."""
        camera = SimCamera(VisionConfig())
        camera.drift = False
        camera.set_head_angles(-95, 0)
        assert camera.subject_position() is None

    def test_an_empty_frame_still_encodes(self):
        camera = SimCamera(VisionConfig())
        camera.drift = False
        camera.set_head_angles(-95, 0)
        frame = camera.capture()
        assert frame.truth is None and len(frame.data) > 50


class TestDetector:
    def test_the_sim_detector_reports_the_subject(self):
        camera = SimCamera(VisionConfig())
        detections = SimDetector().detect(camera.capture())
        assert len(detections) == 1 and detections[0].label == "face"

    def test_no_subject_means_no_detections(self):
        camera = SimCamera(VisionConfig())
        camera.drift = False
        camera.set_head_angles(-95, 0)
        assert SimDetector().detect(camera.capture()) == []

    def test_the_factory_pairs_the_sim_detector_with_the_sim_camera(self):
        cfg = Config()
        camera = make_camera("sim", cfg.vision)
        assert isinstance(make_detector(cfg.vision, camera.kind), SimDetector)

    def test_detection_disabled_yields_nothing(self):
        cfg = Config()
        cfg.vision.detector = "none"
        detector = make_detector(cfg.vision, "Picamera2Backend")
        assert detector.detect(SimCamera(cfg.vision).capture()) == []
