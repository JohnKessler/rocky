"""The dashboard API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rocky.app import RockyApp
from rocky.web.app import create_app


@pytest.fixture
def rocky(config):
    """Built but not started - the TestClient's lifespan starts it, so the
    services and the HTTP handlers share one event loop."""
    return RockyApp(config)


@pytest.fixture
def client(rocky):
    with TestClient(create_app(rocky, manage_lifecycle=True)) as c:
        yield c


class TestPages:
    def test_dashboard_is_served(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Rocky" in response.text

    def test_static_assets_are_served(self, client):
        for path in ("/static/css/dashboard.css", "/static/js/dashboard.js", "/static/js/face.js"):
            assert client.get(path).status_code == 200


class TestStatus:
    def test_status_covers_every_service(self, client):
        data = client.get("/api/status").json()
        for key in ("motion", "face", "vision", "audio", "brain", "bus", "uptime_s"):
            assert key in data

    def test_vocabulary_is_not_hardcoded_in_the_dashboard(self, client):
        """The front end builds its palettes from this, so it must be
        complete or buttons silently disappear."""
        data = client.get("/api/vocabulary").json()
        assert len(data["expressions"]) > 10
        assert all(g["description"] for g in data["gestures"])
        assert all(m["meaning"] for m in data["motifs"])


class TestConfigApi:
    def test_values_and_schema_line_up(self, client):
        data = client.get("/api/config").json()
        assert set(data["values"]) == set(data["schema"])

    def test_a_setting_can_be_changed(self, client):
        response = client.patch("/api/config", json={"path": "face.saccade_rate", "value": 1.2})
        assert response.status_code == 200
        assert response.json()["value"] == pytest.approx(1.2)

    def test_an_out_of_range_value_is_refused_with_a_useful_message(self, client):
        response = client.patch("/api/config", json={"path": "motion.tilt.max_deg", "value": 400})
        assert response.status_code == 422
        assert "less than or equal" in response.json()["detail"]

    def test_an_unknown_setting_is_a_404(self, client):
        response = client.patch("/api/config", json={"path": "motion.warp_factor", "value": 9})
        assert response.status_code == 404

    def test_saving_writes_a_file(self, client, rocky, tmp_path):
        rocky.config.save(tmp_path / "config.toml")
        assert (tmp_path / "config.toml").exists()


class TestControls:
    def test_expression(self, client):
        assert client.post("/api/expression", json={"name": "curious"}).status_code == 200
        assert client.post("/api/expression", json={"name": "smug"}).status_code == 404

    def test_gesture(self, client):
        assert client.post("/api/gesture", json={"name": "nod"}).status_code == 200
        assert client.post("/api/gesture", json={"name": "moonwalk"}).status_code == 404

    def test_chirp(self, client):
        assert client.post("/api/chirp", json={"motif": "greeting"}).status_code == 200
        assert client.post("/api/chirp", json={"motif": "fanfare"}).status_code == 404

    def test_jog_and_centre(self, client):
        jogged = client.post("/api/motion/jog", json={"pan": 30, "tilt": -10}).json()
        assert jogged["pan"] == pytest.approx(30)
        assert client.post("/api/motion/centre").json()["pan"] == 0

    def test_jog_is_clamped_to_the_chassis(self, client):
        """The API must not be a way around the mechanical envelope."""
        jogged = client.post("/api/motion/jog", json={"pan": 500, "tilt": 500}).json()
        assert jogged["pan"] <= 100 and jogged["tilt"] <= 26

    def test_mode(self, client):
        assert client.post("/api/motion/mode", json={"mode": "idle"}).status_code == 200
        assert client.post("/api/motion/mode", json={"mode": "warp"}).status_code == 422


class TestCamera:
    def test_a_frame_is_served_with_the_right_type(self, client):
        response = client.get("/api/camera/frame")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")
        assert len(response.content) > 100


class TestMemoryApi:
    def test_add_list_and_delete(self, client):
        added = client.post("/api/memory", json={"text": "the good screwdriver is in the drawer"})
        assert added.status_code == 200
        fact_id = added.json()["id"]

        listed = client.get("/api/memory").json()
        assert any(f["id"] == fact_id for f in listed["facts"])

        assert client.delete(f"/api/memory/{fact_id}").status_code == 200
        assert client.delete(f"/api/memory/{fact_id}").status_code == 404

    def test_transcript(self, client):
        assert "turns" in client.get("/api/transcript").json()


class TestWebsocket:
    def test_it_opens_with_a_full_snapshot(self, client):
        with client.websocket_connect("/ws") as ws:
            first = ws.receive_json()
            assert first["topic"] == "hello"
            assert "motion" in first["data"]

    def test_events_are_forwarded(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # hello
            client.post("/api/expression", json={"name": "delighted"})
            topics = {ws.receive_json()["topic"] for _ in range(12)}
            assert topics & {"face.expression", "face.frame", "system.telemetry"}

    def test_image_bytes_are_never_inlined(self, client):
        """Frames go over HTTP; putting them in the telemetry socket would
        swamp it."""
        with client.websocket_connect("/ws") as ws:
            for _ in range(20):
                message = ws.receive_json()
                assert "data" not in (message["data"] or {}) or message["topic"] == "hello"
