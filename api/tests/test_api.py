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


def test_tutor_loop_end_to_end():
    # create a learner
    r = client.post("/tutor/learner", json={"display_name": "Test", "language": "en"})
    assert r.status_code == 200
    lid = r.json()["id"]
    assert r.json()["signs_started"] == 0

    # first lesson: all new signs
    lesson = client.get(f"/tutor/learner/{lid}/lesson", params={"size": 5}).json()
    assert lesson["new"] and not lesson["review"]

    # study a sign -> Good
    sign_id = lesson["new"][0]
    rev = client.post(f"/tutor/learner/{lid}/review", json={"sign_id": sign_id, "rating": 3})
    assert rev.status_code == 200
    assert rev.json()["reps"] == 1
    assert rev.json()["state"] in {"learning", "review"}  # new -> learning on first review

    # state reflects the studied sign
    state = client.get(f"/tutor/learner/{lid}").json()
    assert state["signs_started"] == 1
    assert sign_id in state["mastery"]
    assert "today_bs" in state


def test_score_demo_runs_dtw_and_critique():
    if not client.get("/tutor/score/status").json()["references_available"]:
        return  # references not built in this env
    # A closer attempt (low noise) must score higher than a sloppy one (high noise), and
    # both must return a concrete parameter target + localized feedback.
    good = client.post("/tutor/score-demo", params={"sign_id": "NSL_0001", "noise": 0.02}).json()
    bad = client.post("/tutor/score-demo", params={"sign_id": "NSL_0001", "noise": 0.6}).json()
    assert 0 <= bad["overall"] < good["overall"] <= 100
    for r in (good, bad):
        assert r["feedback_message"]
        assert r["feedback_target"] in {"handshape", "location", "movement", "orientation"}
    # per-parameter error decomposition is present
    assert set(good["parameters"]) == {"handshape", "location", "movement", "orientation"}


def test_score_demo_unknown_sign_404():
    assert client.post("/tutor/score-demo", params={"sign_id": "NSL_9999"}).status_code == 404


def test_tutor_unknown_learner_404():
    assert client.get("/tutor/learner/999999").status_code == 404


def test_interpret_sign_to_text():
    r = client.post(
        "/interpret/sign-to-text",
        json={"sign_ids": ["NSL_0001", "NSL_0002"], "language": "ne"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["gloss"] == "HELLO THANK-YOU"
    assert body["text"] == body["text_ne"] and body["text_ne"]
    assert body["text_en"]  # both languages returned regardless of requested one


def test_interpret_skips_unknown_signs():
    r = client.post("/interpret/sign-to-text", json={"sign_ids": ["NSL_0001", "NSL_9999"]})
    assert r.status_code == 200
    assert r.json()["unknown"] == ["NSL_9999"]


def test_produce_single_sign():
    r = client.get("/produce/sign", params={"sign_id": "NSL_0001"})
    assert r.status_code == 200
    assert len(r.json()["steps"]) == 1
    assert client.get("/produce/sign", params={"sign_id": "NSL_9999"}).status_code == 404


def test_eval_models_and_ratings():
    r = client.get("/eval/models")
    assert r.status_code == 200
    assert "recognition" in r.json() and "fingerspelling" in r.json()

    # submit an intelligibility rating and see it reflected in the summary
    assert client.post("/eval/rating", json={"sign_id": "NSL_0001", "score": 5}).status_code == 200
    summary = client.get("/eval/ratings/summary").json()
    assert summary["count"] >= 1
    assert summary["mean_score"] is not None


def test_eval_rating_validates_score():
    assert client.post("/eval/rating", json={"sign_id": "NSL_0001", "score": 9}).status_code == 422


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
