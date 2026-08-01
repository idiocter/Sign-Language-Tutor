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


def test_inference_status():
    r = client.get("/inference/status")
    assert r.status_code == 200
    assert "ready" in r.json()


def test_inference_demo_when_model_present():
    # If the interim model has been trained/exported, the demo loop should recognize a
    # synthesized attempt. Skip cleanly if no model artifacts are present.
    if not client.get("/inference/status").json()["ready"]:
        return
    r = client.post("/inference/demo", params={"sign_id": "NSL_0001"})
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == "NSL_0001"
    assert body["predictions"]


def test_inference_ws():
    with client.websocket_connect("/inference/ws") as ws:
        ws.send_text('{"features": []}')
        msg = ws.receive_json()
        assert "ready" in msg and "predictions" in msg


def test_produce_text_to_sign():
    r = client.post("/produce", json={"text": "hello thank you", "language": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["steps"], "expected at least one signed step"
    assert body["has_facial_motion"] is True  # Phase 2: face must move
    first = body["steps"][0]
    assert first["pose"]["right_hand"]["location"]  # procedural pose present
    assert "blendshapes" in first["facial"]


def test_produce_falls_back_to_procedural_when_no_glb():
    # No authored .glb clips exist, so every step should have clip_ref = null.
    r = client.post("/produce", json={"text": "hello", "language": "en"})
    assert all(s["clip_ref"] is None for s in r.json()["steps"])


def test_fingerspell_status():
    r = client.get("/inference/fingerspell/status")
    assert r.status_code == 200 and "ready" in r.json()


def test_fingerspell_spell_word():
    if not client.get("/inference/fingerspell/status").json()["ready"]:
        return
    r = client.get("/inference/fingerspell/spell", params={"word": "namaste"})
    assert r.status_code == 200
    body = r.json()
    assert body["devanagari"]  # transliterated
    assert body["chars"], "expected recognized characters"
    assert 0.0 <= body["accuracy"] <= 1.0


def test_clip_manifest():
    r = client.get("/clips/manifest")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 50
    assert body["authored"] + body["procedural"] == body["total"]
