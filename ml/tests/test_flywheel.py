"""The recursive learning loop: gate → candidate → review → promote → next generation.

Every test runs against tmp directories, so the real dataset is never touched.
"""

from __future__ import annotations

import numpy as np
import pytest

from signbridge import flywheel
from signbridge.config import FEATURE_DIM, SEQ_LEN


def _take(seed: int = 0) -> np.ndarray:
    """A take that passes the curator: long enough, moving, with hand landmarks."""
    return np.random.default_rng(seed).normal(size=(SEQ_LEN, FEATURE_DIM)).astype(np.float32)


@pytest.fixture()
def store(tmp_path):
    return flywheel.CandidateStore(root=tmp_path / "candidates", raw_dir=tmp_path / "raw")


def _seed_raw(raw_dir, sign_id: str, signers: list[str], per_signer: int = 2) -> None:
    """Existing studio takes, named the way the capture tool names them."""
    for signer in signers:
        for i in range(per_signer):
            d = raw_dir / sign_id
            d.mkdir(parents=True, exist_ok=True)
            np.save(d / f"{sign_id}__{signer}__2026080{i + 1}_120000.npy", _take(hash(signer) % 99))


# --- signer identity --------------------------------------------------------

def test_learner_signer_ids_are_namespaced_and_underscore_free():
    signer = flywheel.contributor_signer_id("learner_7")
    assert signer.startswith("L")
    # "_" is the field separator in take filenames — one here would corrupt the parse.
    assert "_" not in signer
    assert flywheel.is_learner_signer(signer)
    assert not flywheel.is_learner_signer("S03")


def test_blank_contributor_is_rejected():
    with pytest.raises(ValueError):
        flywheel.contributor_signer_id("___")


# --- the gate ---------------------------------------------------------------

def test_gate_accepts_a_good_confident_take():
    decision = flywheel.gate(
        _take(), sign_id="NSL_0001", score=92.0, confidence=0.97, recognized_sign_id="NSL_0001"
    )
    assert decision.accepted and not decision.reasons


def test_gate_rejects_low_score_and_low_confidence():
    sloppy = flywheel.gate(_take(), sign_id="NSL_0001", score=40.0, confidence=0.99)
    unsure = flywheel.gate(_take(), sign_id="NSL_0001", score=99.0, confidence=0.10)
    assert not sloppy.accepted and any("score_below" in r for r in sloppy.reasons)
    assert not unsure.accepted and any("confidence_below" in r for r in unsure.reasons)


def test_gate_rejects_a_take_the_model_reads_as_another_sign():
    """Whoever is wrong, the label is unreliable — this is the take that would teach the
    model its own mistake."""
    decision = flywheel.gate(
        _take(), sign_id="NSL_0001", score=95.0, confidence=0.99, recognized_sign_id="NSL_0002"
    )
    assert not decision.accepted
    assert any("NSL_0002" in r for r in decision.reasons)


def test_gate_applies_curator_quality_flags():
    static = np.zeros((SEQ_LEN, FEATURE_DIM), dtype=np.float32)
    decision = flywheel.gate(static, sign_id="NSL_0001", score=99.0, confidence=0.99)
    assert not decision.accepted
    assert "near_static" in decision.flags and "no_hands" in decision.flags


def test_gate_rejects_a_wrong_shaped_sequence():
    decision = flywheel.gate(
        np.zeros((SEQ_LEN, 7), dtype=np.float32), sign_id="NSL_0001", score=99.0, confidence=0.99
    )
    assert not decision.accepted and decision.reasons[0].startswith("bad_shape")


# --- staging ----------------------------------------------------------------

def test_staging_requires_explicit_consent(store):
    with pytest.raises(PermissionError):
        store.stage(
            _take(), sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99,
            consent=False,
        )
    assert store.list_candidates() == []


def test_staged_candidate_is_pending_and_named_for_the_pipeline(store):
    candidate = store.stage(
        _take(), sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99, consent=True
    )
    assert candidate.status == "pending"
    assert candidate.candidate_id.startswith("NSL_0001__Ll7__")
    assert store.sequence_path(candidate).exists()
    # The name must parse as a take, or promotion could not be a plain copy.
    from signbridge.preprocessing import Sample

    parsed = Sample.from_path(store.sequence_path(candidate))
    assert parsed is not None and parsed.sign_id == "NSL_0001" and parsed.signer_id == "Ll7"


def test_two_takes_in_one_second_stay_one_signer(store):
    """A suffixed signer ID would split one person in two — exactly what the
    signer-independent split forbids."""
    a = store.stage(
        _take(1), sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99, consent=True
    )
    b = store.stage(
        _take(2), sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99, consent=True
    )
    assert a.candidate_id != b.candidate_id
    assert a.signer_id == b.signer_id == "Ll7"


def test_duplicate_takes_by_the_same_contributor_are_detected(store):
    seq = _take(3)
    store.stage(
        seq, sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99, consent=True
    )
    assert store.duplicate_of(seq.copy(), sign_id="NSL_0001", contributor="l7") is not None
    # A different learner signing the same sign well is signal, not a duplicate.
    assert store.duplicate_of(seq.copy(), sign_id="NSL_0001", contributor="l9") is None
    assert store.duplicate_of(_take(4), sign_id="NSL_0001", contributor="l7") is None


# --- review -----------------------------------------------------------------

def test_review_records_who_approved_what(store):
    candidate = store.stage(
        _take(), sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99, consent=True
    )
    reviewed = store.review(candidate.candidate_id, status="approved", reviewer="advisor-1")
    assert reviewed.status == "approved" and reviewed.reviewed_by == "advisor-1"
    assert store.list_candidates(status="pending") == []
    assert len(store.list_candidates(status="approved")) == 1


def test_review_rejects_unknown_ids_and_bad_statuses(store):
    candidate = store.stage(
        _take(), sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99, consent=True
    )
    with pytest.raises(KeyError):
        store.review("nope", status="approved", reviewer="r")
    with pytest.raises(ValueError):
        store.review(candidate.candidate_id, status="maybe", reviewer="r")


# --- promotion --------------------------------------------------------------

def _approved(store, sign_id="NSL_0001", contributor="l7", seed=0):
    candidate = store.stage(
        _take(seed), sign_id=sign_id, contributor=contributor, score=95.0, confidence=0.99,
        consent=True,
    )
    return store.review(candidate.candidate_id, status="approved", reviewer="advisor-1")


def test_nothing_is_promoted_without_approval(store):
    store.stage(
        _take(), sign_id="NSL_0001", contributor="l7", score=95.0, confidence=0.99, consent=True
    )
    _seed_raw(store.raw_dir, "NSL_0001", ["S01", "S02"], per_signer=5)
    assert store.promote().promoted == []


def test_learner_data_cannot_found_a_class(store):
    """A sign with no studio signers would be learned from the model's own predictions."""
    _approved(store)
    result = store.promote(dry_run=True)
    assert result.promoted == []
    assert "studio signer" in result.skipped[0][1]


def test_approved_take_is_promoted_and_bumps_the_generation(store):
    _seed_raw(store.raw_dir, "NSL_0001", ["S01", "S02"], per_signer=5)
    candidate = _approved(store)
    assert store.generation == 0

    dry = store.promote(dry_run=True)
    assert dry.promoted == [candidate.candidate_id]
    assert not (store.raw_dir / "NSL_0001" / f"{candidate.candidate_id}.npy").exists()
    assert store.generation == 0, "a dry run must not advance the loop"

    live = store.promote(dry_run=False)
    assert live.promoted == [candidate.candidate_id]
    assert (store.raw_dir / "NSL_0001" / f"{candidate.candidate_id}.npy").exists()
    assert store.generation == 1
    assert store.get(candidate.candidate_id).status == "promoted"
    # Already in the training set — a second run must not copy it again.
    assert store.promote(dry_run=False).promoted == []


def test_no_single_signer_may_dominate_a_sign(store):
    """PROJECT_PLAN.md's named failure mode: a model that works for one person."""
    _seed_raw(store.raw_dir, "NSL_0001", ["S01", "S02"], per_signer=1)
    for seed in range(4):
        _approved(store, seed=seed)
    result = store.promote(dry_run=False)
    assert result.promoted, "the first learner take should still get in"
    assert result.skipped, "but not all four — the share cap has to bite"
    assert any("cap" in reason for _, reason in result.skipped)

    from signbridge.preprocessing import discover

    signers = [s.signer_id for s in discover(store.raw_dir) if s.sign_id == "NSL_0001"]
    learner_share = sum(1 for s in signers if flywheel.is_learner_signer(s)) / len(signers)
    assert learner_share <= flywheel.DEFAULT_MAX_SIGNER_SHARE


def test_promoted_candidate_records_the_generation_that_admitted_it(store):
    _seed_raw(store.raw_dir, "NSL_0001", ["S01", "S02"], per_signer=5)
    first = _approved(store, seed=1)
    store.promote(dry_run=False)
    second = _approved(store, seed=2)
    assert first.generation == 0
    assert second.generation == 1, "a take gathered after a retrain belongs to the next generation"


# --- reporting --------------------------------------------------------------

def test_readiness_reports_the_state_of_the_loop(store):
    _seed_raw(store.raw_dir, "NSL_0001", ["S01", "S02", "S03", "S04", "S05"], per_signer=1)
    _seed_raw(store.raw_dir, "NSL_0002", ["S01"], per_signer=1)
    report = store.readiness()
    assert report["generation"] == 0
    assert report["signs_ready_for_training"] == 1  # NSL_0001 has 5 signers, NSL_0002 has 1
    assert report["retrain_recommended"] is False

    _approved(store)
    assert store.readiness()["retrain_recommended"] is True
    assert store.readiness()["candidates"]["approved"] == 1
