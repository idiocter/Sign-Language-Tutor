"""Smoke tests for the API surface using FastAPI's TestClient."""

from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from signbridge.config import FEATURE_DIM, SEQ_LEN

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_list_signs():
    r = client.get("/signs")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 50
    assert body[0]["sign_id"].startswith("NSL_")


def test_get_sign_404():
    assert client.get("/signs/NSL_9999").status_code == 404


def test_transliterate():
    r = client.post("/signs/transliterate", json={"text": "namaste"})
    assert r.status_code == 200
    assert r.json()["devanagari"] == "नमस्ते"


def test_lesson():
    r = client.post("/tutor/lesson", json={"language": "en", "lesson_size": 5})
    assert r.status_code == 200
    body = r.json()
    assert len(body["new"]) <= 5


def test_review_advances_due():
    r = client.post("/tutor/review", json={"sign_id": "NSL_0001", "rating": 3})
    assert r.status_code == 200
    assert r.json()["reps"] == 1


def test_score_roundtrip():
    ref = np.random.default_rng(0).normal(size=(SEQ_LEN, FEATURE_DIM)).tolist()
    r = client.post(
        "/tutor/score", json={"language": "ne", "learner": ref, "reference": ref}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] > 95.0
    assert body["feedback_message"]  # localized (Nepali) text present


def test_score_rejects_bad_shape():
    r = client.post("/tutor/score", json={"learner": [[1, 2, 3]], "reference": [[1, 2, 3]]})
    assert r.status_code == 422


def test_inference_ws_stub():
    with client.websocket_connect("/ws/inference") as ws:
        ws.send_text('{"frames": [[0.0]]}')
        msg = ws.receive_json()
        assert msg["stub"] is True and msg["sign_id"].startswith("NSL_")
