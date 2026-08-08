"""The recursive learning loop, over HTTP.

    contribute → gate → candidate queue → human review → promote → retrain → …

``/flywheel/contribute`` is the only public step. Everything that can change what the model
trains on (``/review``, ``/promote``) needs the reviewer token, because approving data is
the one action in this API that reaches into the dataset. See
:mod:`signbridge.flywheel` for the invariants the gate and the promoter enforce.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from signbridge import flywheel
from signbridge.config import FEATURE_DIM
from signbridge.models.linear_model import pool_features
from signbridge.scoring.dtw import score_attempt

from .. import references
from ..config import settings
from ..inference_engine import get_engine
from .signs import _dictionary

router = APIRouter(prefix="/flywheel", tags=["flywheel"])

_store = flywheel.CandidateStore()


def get_store() -> flywheel.CandidateStore:
    """Injectable so tests (and a reviewer on a copy) never touch the real dataset."""
    return _store


def require_reviewer(x_reviewer_token: str | None = Header(default=None)) -> str:
    """Gate the dataset-mutating endpoints behind a shared token.

    Default-deny: with ``SIGNBRIDGE_REVIEWER_TOKEN`` unset there is no way to approve or
    promote anything. Contributions still queue up safely; they just wait for a reviewer.
    """
    if not settings.reviewer_token:
        raise HTTPException(
            503,
            "review is disabled — set SIGNBRIDGE_REVIEWER_TOKEN to enable approving "
            "learner data into the training set",
        )
    if x_reviewer_token != settings.reviewer_token:
        raise HTTPException(401, "invalid X-Reviewer-Token")
    return x_reviewer_token


class ContributeIn(BaseModel):
    sign_id: str
    contributor: str = Field(..., description="stable per-learner id, e.g. 'learner-7'")
    landmarks: list[list[float]] = Field(..., description="(frames, FEATURE_DIM), normalized")
    consent: bool = Field(
        default=False,
        description="learner explicitly agreed to donate this take for training",
    )
    score: float | None = Field(default=None, description="DTW overall; computed if omitted")
    confidence: float | None = Field(default=None, description="from on-device recognition")


class ContributeOut(BaseModel):
    accepted: bool
    reasons: list[str]
    flags: list[str]
    score: float
    confidence: float
    candidate_id: str | None = None
    duplicate_of: str | None = None


class ReviewIn(BaseModel):
    status: str = Field(..., description="approved | rejected")
    reviewer: str
    note: str | None = None


class PromoteIn(BaseModel):
    dry_run: bool = True
    min_studio_signers: int = flywheel.DEFAULT_MIN_STUDIO_SIGNERS
    max_signer_share: float = Field(default=flywheel.DEFAULT_MAX_SIGNER_SHARE, gt=0.0, le=1.0)


@router.get("/status")
def status(store: flywheel.CandidateStore = Depends(get_store)) -> dict:
    """Where the loop stands: generation, queue depth, and whether a retrain is due."""
    report = store.readiness(_dictionary())
    report["review_enabled"] = bool(settings.reviewer_token)
    report["references_available"] = references.available()
    report["recognition_ready"] = get_engine().ready
    return report


@router.post("/contribute", response_model=ContributeOut)
def contribute(
    payload: ContributeIn, store: flywheel.CandidateStore = Depends(get_store)
) -> ContributeOut:
    """Offer a scored attempt as a training candidate. Consent is required and explicit."""
    if not payload.consent:
        raise HTTPException(403, "consent is required to donate a take for training")

    learner = np.asarray(payload.landmarks, dtype=np.float32)
    if learner.ndim != 2 or learner.shape[1] != FEATURE_DIM:
        raise HTTPException(422, f"landmarks must be (frames, {FEATURE_DIM}); got {learner.shape}")

    # Score against the stored reference unless the client already did (in-browser path).
    score = payload.score
    if score is None:
        reference = references.load_reference(payload.sign_id)
        if reference is None:
            raise HTTPException(
                404, f"no reference for {payload.sign_id} — run build_references.py or send score"
            )
        score = score_attempt(learner, reference).overall

    # Cross-check the label against the recognizer. Without that second opinion we would be
    # training the model on nothing but its own say-so, so refuse rather than guess.
    confidence = payload.confidence
    recognized: str | None = None
    engine = get_engine()
    if engine.ready:
        predictions = engine.predict(pool_features(learner).tolist(), top_k=1)
        if predictions:
            recognized = predictions[0]["sign_id"]
            if confidence is None:
                confidence = predictions[0]["confidence"]
    if confidence is None:
        return ContributeOut(
            accepted=False,
            reasons=["recognition_unavailable"],
            flags=[],
            score=round(float(score), 2),
            confidence=0.0,
        )

    decision = flywheel.gate(
        learner,
        sign_id=payload.sign_id,
        score=float(score),
        confidence=float(confidence),
        recognized_sign_id=recognized,
    )
    duplicate_of = None
    if decision.accepted:
        duplicate_of = store.duplicate_of(
            learner, sign_id=payload.sign_id, contributor=payload.contributor
        )
        if duplicate_of is not None:
            decision.accepted = False
            decision.reasons.append(f"duplicate_of:{duplicate_of}")

    candidate_id = None
    if decision.accepted:
        candidate = store.stage(
            learner,
            sign_id=payload.sign_id,
            contributor=payload.contributor,
            score=float(score),
            confidence=float(confidence),
            consent=payload.consent,
            flags=decision.flags,
        )
        candidate_id = candidate.candidate_id

    return ContributeOut(
        accepted=decision.accepted,
        reasons=decision.reasons,
        flags=decision.flags,
        score=round(float(score), 2),
        confidence=round(float(confidence), 4),
        candidate_id=candidate_id,
        duplicate_of=duplicate_of,
    )


@router.get("/queue")
def queue(
    status: str = "pending",
    sign_id: str | None = None,
    limit: int = 50,
    store: flywheel.CandidateStore = Depends(get_store),
) -> dict:
    """Candidates awaiting (or past) review. Metadata only — no landmarks over the wire."""
    try:
        candidates = store.list_candidates(status=status, sign_id=sign_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "status": status,
        "count": len(candidates),
        "candidates": [c.as_dict() for c in candidates[:limit]],
    }


@router.post("/review/{candidate_id}")
def review(
    candidate_id: str,
    payload: ReviewIn,
    _: str = Depends(require_reviewer),
    store: flywheel.CandidateStore = Depends(get_store),
) -> dict:
    try:
        candidate = store.review(
            candidate_id, status=payload.status, reviewer=payload.reviewer, note=payload.note
        )
    except KeyError:
        raise HTTPException(404, f"unknown candidate {candidate_id}") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return candidate.as_dict()


@router.post("/promote")
def promote(
    payload: PromoteIn,
    _: str = Depends(require_reviewer),
    store: flywheel.CandidateStore = Depends(get_store),
) -> dict:
    """Move approved candidates into the training set and start the next generation.

    Defaults to a dry run: see what would move before anything does.
    """
    result = store.promote(
        min_studio_signers=payload.min_studio_signers,
        max_signer_share=payload.max_signer_share,
        dry_run=payload.dry_run,
    )
    return result.as_dict()
