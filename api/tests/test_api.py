"""Smoke tests for the API surface using FastAPI's TestClient."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.references import REF_DIR
from app.routers import flywheel as flywheel_router
from signbridge import flywheel
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


# --- Recursive remediation --------------------------------------------------


def test_remediation_returns_a_foundation_first_ladder():
    r = client.post(
        "/tutor/remediation",
        json={"sign_id": "NSL_0003", "failed_parameter": "handshape", "language": "en"},
    )
    assert r.status_code == 200
    body = r.json()
    steps = body["steps"]
    assert steps and steps[-1]["kind"] == "target" and steps[-1]["depth"] == 0
    assert steps[0]["depth"] == body["depth_reached"]  # deepest drill first
    assert all(s["instruction"] for s in steps)
    assert len([s for s in steps if s["kind"] == "component"]) == 1


def test_remediation_bottoms_out_on_mastered_signs():
    """Mastering the neighbours should shorten the ladder, not lengthen it."""
    cold = client.post(
        "/tutor/remediation", json={"sign_id": "NSL_0003", "failed_parameter": "handshape"}
    ).json()
    warm = client.post(
        "/tutor/remediation",
        json={
            "sign_id": "NSL_0003",
            "failed_parameter": "handshape",
            "mastery": {"NSL_0005": 1.0, "NSL_0030": 1.0},
        },
    ).json()
    assert any(s["kind"] == "foundation" for s in warm["steps"])
    assert len(warm["steps"]) <= len(cold["steps"])


def test_remediation_rejects_unknown_sign_and_parameter():
    assert client.post("/tutor/remediation", json={"sign_id": "NSL_9999"}).status_code == 404
    bad = client.post(
        "/tutor/remediation", json={"sign_id": "NSL_0001", "failed_parameter": "vibe"}
    )
    assert bad.status_code == 422


def test_lesson_trades_new_signs_for_a_drill_ladder():
    plain = client.post("/tutor/lesson", json={"lesson_size": 5}).json()
    struggling = client.post(
        "/tutor/lesson", json={"lesson_size": 5, "struggling": [["NSL_0001", "handshape"]]}
    ).json()
    assert not plain["remediation"] and struggling["remediation"]
    assert len(struggling["new"]) < len(plain["new"])


def test_learner_attempt_records_failure_and_drives_the_next_lesson():
    if not client.get("/tutor/score/status").json()["references_available"]:
        return  # references not built in this env
    lid = client.post("/tutor/learner", json={"display_name": "Struggler"}).json()["id"]
    ref = np.load(REF_DIR / "NSL_0001.npy")
    sloppy = (ref + np.random.default_rng(0).normal(0, 0.8, ref.shape)).astype(np.float32)

    r = client.post(f"/tutor/learner/{lid}/attempt", json={"sign_id": "NSL_0001", "learner": sloppy.tolist()})
    assert r.status_code == 200
    body = r.json()
    assert body["score"]["passed"] is False
    assert body["remediation"]["target_sign_id"] == "NSL_0001"
    assert body["remediation"]["failed_parameter"] == body["score"]["feedback_target"]

    # The recorded failure is what makes the *next* lesson recursive.
    lesson = client.get(f"/tutor/learner/{lid}/lesson", params={"size": 5}).json()
    assert any(s["sign_id"] == "NSL_0001" for s in lesson["remediation"])

    # And it can be re-requested directly, defaulting to the parameter that failed.
    direct = client.get(
        f"/tutor/learner/{lid}/remediation", params={"sign_id": "NSL_0001"}
    ).json()
    assert direct["failed_parameter"] == body["score"]["feedback_target"]


def test_learner_attempt_unknown_learner_404():
    r = client.post("/tutor/learner/999999/attempt", json={"sign_id": "NSL_0001", "learner": [[0.0]]})
    assert r.status_code == 404


# --- Flywheel (recursive learning loop) -------------------------------------


class _NoModel:
    """Stand-in for an unloaded recognition model, so the gate tests are deterministic."""

    ready = False


@pytest.fixture()
def flywheel_client(tmp_path, monkeypatch):
    """A client whose flywheel writes to tmp_path and whose recognizer is absent."""
    store = flywheel.CandidateStore(root=tmp_path / "candidates", raw_dir=tmp_path / "raw")
    monkeypatch.setattr(flywheel_router, "get_engine", lambda: _NoModel())
    app.dependency_overrides[flywheel_router.get_store] = lambda: store
    try:
        yield client, store
    finally:
        app.dependency_overrides.pop(flywheel_router.get_store, None)


def _take(seed: int = 0) -> list[list[float]]:
    return np.random.default_rng(seed).normal(size=(SEQ_LEN, FEATURE_DIM)).tolist()


def test_flywheel_status_reports_the_loop(flywheel_client):
    c, _ = flywheel_client
    body = c.get("/flywheel/status").json()
    assert body["generation"] == 0
    assert set(body["candidates"]) == {"pending", "approved", "rejected", "promoted"}
    assert body["signs_total"] >= 50


def test_contribute_requires_explicit_consent(flywheel_client):
    c, store = flywheel_client
    r = c.post(
        "/flywheel/contribute",
        json={"sign_id": "NSL_0001", "contributor": "l7", "landmarks": _take(),
              "score": 95.0, "confidence": 0.99},
    )
    assert r.status_code == 403
    assert store.list_candidates() == []


def test_contribute_stages_a_good_take_and_explains_a_bad_one(flywheel_client):
    c, store = flywheel_client
    good = c.post(
        "/flywheel/contribute",
        json={"sign_id": "NSL_0001", "contributor": "l7", "landmarks": _take(1),
              "score": 95.0, "confidence": 0.99, "consent": True},
    ).json()
    assert good["accepted"] and good["candidate_id"].startswith("NSL_0001__Ll7__")

    sloppy = c.post(
        "/flywheel/contribute",
        json={"sign_id": "NSL_0001", "contributor": "l8", "landmarks": _take(2),
              "score": 41.0, "confidence": 0.99, "consent": True},
    ).json()
    assert not sloppy["accepted"] and sloppy["candidate_id"] is None
    assert any("score_below" in reason for reason in sloppy["reasons"])

    queued = c.get("/flywheel/queue", params={"status": "pending"}).json()
    assert queued["count"] == 1


def test_contribute_rejects_a_repeat_of_the_same_take(flywheel_client):
    c, _ = flywheel_client
    take = _take(3)
    body = {"sign_id": "NSL_0001", "contributor": "l7", "landmarks": take,
            "score": 95.0, "confidence": 0.99, "consent": True}
    assert c.post("/flywheel/contribute", json=body).json()["accepted"]
    repeat = c.post("/flywheel/contribute", json=body).json()
    assert not repeat["accepted"] and repeat["duplicate_of"]


def test_review_and_promote_are_closed_without_a_reviewer_token(flywheel_client):
    c, store = flywheel_client
    c.post(
        "/flywheel/contribute",
        json={"sign_id": "NSL_0001", "contributor": "l7", "landmarks": _take(4),
              "score": 95.0, "confidence": 0.99, "consent": True},
    )
    cid = store.list_candidates()[0].candidate_id
    assert settings.reviewer_token is None
    assert c.post(f"/flywheel/review/{cid}", json={"status": "approved", "reviewer": "x"}).status_code == 503
    assert c.post("/flywheel/promote", json={"dry_run": True}).status_code == 503
    assert store.get(cid).status == "pending"


def test_full_loop_from_contribution_to_promotion(flywheel_client, monkeypatch):
    c, store = flywheel_client
    monkeypatch.setattr(settings, "reviewer_token", "s3cret")
    # Two studio signers already recorded this sign — learner data may augment it.
    for signer in ("S01", "S02"):
        d = store.raw_dir / "NSL_0001"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            np.save(d / f"NSL_0001__{signer}__2026080{i + 1}_120000.npy",
                    np.random.default_rng(hash(signer) % 99).normal(size=(SEQ_LEN, FEATURE_DIM)).astype(np.float32))

    cid = c.post(
        "/flywheel/contribute",
        json={"sign_id": "NSL_0001", "contributor": "l7", "landmarks": _take(5),
              "score": 95.0, "confidence": 0.99, "consent": True},
    ).json()["candidate_id"]

    assert c.post(f"/flywheel/review/{cid}", json={"status": "approved", "reviewer": "advisor"},
                  headers={"X-Reviewer-Token": "wrong"}).status_code == 401

    headers = {"X-Reviewer-Token": "s3cret"}
    approved = c.post(f"/flywheel/review/{cid}",
                      json={"status": "approved", "reviewer": "advisor"}, headers=headers).json()
    assert approved["status"] == "approved" and approved["reviewed_by"] == "advisor"
    assert c.get("/flywheel/status").json()["retrain_recommended"] is True

    dry = c.post("/flywheel/promote", json={"dry_run": True}, headers=headers).json()
    assert dry["promoted"] == [cid] and dry["dry_run"] is True
    assert store.generation == 0

    live = c.post("/flywheel/promote", json={"dry_run": False}, headers=headers).json()
    assert live["promoted"] == [cid]
    assert (store.raw_dir / "NSL_0001" / f"{cid}.npy").exists()
    assert c.get("/flywheel/status").json()["generation"] == 1


def test_promotion_refuses_to_found_a_class_on_learner_data(flywheel_client, monkeypatch):
    c, store = flywheel_client
    monkeypatch.setattr(settings, "reviewer_token", "s3cret")
    headers = {"X-Reviewer-Token": "s3cret"}
    cid = c.post(
        "/flywheel/contribute",
        json={"sign_id": "NSL_0002", "contributor": "l7", "landmarks": _take(6),
              "score": 95.0, "confidence": 0.99, "consent": True},
    ).json()["candidate_id"]
    c.post(f"/flywheel/review/{cid}", json={"status": "approved", "reviewer": "advisor"}, headers=headers)

    result = c.post("/flywheel/promote", json={"dry_run": False}, headers=headers).json()
    assert result["promoted"] == []
    assert "studio signer" in result["skipped"][0]["reason"]


def test_contribute_refuses_when_it_cannot_check_the_label(flywheel_client):
    """No recognizer and no client-side confidence: nothing to cross-check the label
    against, so the take is not kept."""
    c, store = flywheel_client
    body = c.post(
        "/flywheel/contribute",
        json={"sign_id": "NSL_0001", "contributor": "l7", "landmarks": _take(7),
              "score": 95.0, "consent": True},
    ).json()
    assert not body["accepted"] and body["reasons"] == ["recognition_unavailable"]
    assert store.list_candidates() == []
