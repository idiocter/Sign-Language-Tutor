"""Tutor endpoints: lesson sequencing, spaced-repetition review, movement scoring."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from signbridge.agents.base import AgentContext
from signbridge.agents.critique import CritiqueAgent
from signbridge.agents.curriculum import CurriculumAgent, LessonRequest
from signbridge.agents.remediation import RemediationAgent, RemediationPlan, RemediationRequest
from signbridge.config import FEATURE_DIM
from signbridge.scoring.dtw import score_attempt
from signbridge.tutor.scheduler import Rating, ReviewCard, Scheduler

from .. import references, tutor_store
from ..db import get_db
from ..schemas import (
    DrillStepOut,
    LessonIn,
    LessonOut,
    RemediationIn,
    RemediationOut,
    ReviewIn,
    ReviewOut,
    ScoreIn,
    ScoreOut,
)
from .signs import _dictionary

router = APIRouter(prefix="/tutor", tags=["tutor"])

_scheduler = Scheduler()
_critique = CritiqueAgent()


def _steps_out(steps) -> list[DrillStepOut]:
    return [DrillStepOut(**s.__dict__) for s in steps]


def _plan_out(plan: RemediationPlan) -> RemediationOut:
    return RemediationOut(
        target_sign_id=plan.target_sign_id,
        failed_parameter=plan.failed_parameter,
        depth_reached=plan.depth_reached,
        truncated=plan.truncated,
        steps=_steps_out(plan.steps),
    )


@router.post("/lesson", response_model=LessonOut)
def next_lesson(payload: LessonIn) -> LessonOut:
    agent = CurriculumAgent(_dictionary())
    ctx = AgentContext(language=payload.language, mastery=payload.mastery)
    lesson = agent.run(
        LessonRequest(
            lesson_size=payload.lesson_size,
            due_sign_ids=payload.due_sign_ids,
            struggling=[tuple(pair) for pair in payload.struggling],
        ),
        ctx,
    )
    return LessonOut(
        review=lesson.review,
        new=lesson.new,
        difficulty=lesson.difficulty,
        remediation=_steps_out(lesson.remediation),
    )


@router.post("/remediation", response_model=RemediationOut)
def remediation(payload: RemediationIn) -> RemediationOut:
    """Recursive drill ladder for a failed sign, foundation-first.

    Descends the sign's prerequisites and phonological neighbours until it reaches
    something the learner has already mastered, then re-ascends to the failed sign.
    """
    agent = RemediationAgent(_dictionary())
    ctx = AgentContext(language=payload.language, mastery=payload.mastery)
    try:
        plan = agent.run(RemediationRequest(payload.sign_id, payload.failed_parameter), ctx)
    except KeyError:
        raise HTTPException(404, f"unknown sign {payload.sign_id}") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _plan_out(plan)


@router.post("/review", response_model=ReviewOut)
def submit_review(payload: ReviewIn) -> ReviewOut:
    card = ReviewCard(
        sign_id=payload.sign_id,
        stability=payload.stability,
        difficulty=payload.difficulty,
        reps=payload.reps,
        lapses=payload.lapses,
        state=payload.state,
    )
    updated = _scheduler.review(card, Rating(payload.rating))
    return ReviewOut(
        sign_id=updated.sign_id,
        due=updated.due.isoformat(),
        stability=updated.stability,
        difficulty=updated.difficulty,
        reps=updated.reps,
        lapses=updated.lapses,
        state=updated.state,
    )


# --- Stateful tutor loop (Phase 3) ------------------------------------------


class LearnerIn(BaseModel):
    display_name: str = "Learner"
    language: str = "en"


class ReviewSubmit(BaseModel):
    sign_id: str
    rating: int  # 1=Again 2=Hard 3=Good 4=Easy


@router.post("/learner")
def create_learner(payload: LearnerIn, db: Session = Depends(get_db)) -> dict:
    learner = tutor_store.create_learner(db, payload.display_name, payload.language)
    return tutor_store.learner_state(db, learner)


@router.get("/learner/{learner_id}")
def get_learner(learner_id: int, db: Session = Depends(get_db)) -> dict:
    learner = tutor_store.get_learner(db, learner_id)
    if learner is None:
        raise HTTPException(404, "unknown learner")
    return tutor_store.learner_state(db, learner)


@router.get("/learner/{learner_id}/lesson", response_model=LessonOut)
def learner_lesson(learner_id: int, size: int = 8, db: Session = Depends(get_db)) -> LessonOut:
    learner = tutor_store.get_learner(db, learner_id)
    if learner is None:
        raise HTTPException(404, "unknown learner")
    state = tutor_store.learner_state(db, learner)
    agent = CurriculumAgent(_dictionary())
    ctx = AgentContext(language=learner.language, mastery=state["mastery"])
    lesson = agent.run(
        LessonRequest(
            lesson_size=size,
            due_sign_ids=tutor_store.due_sign_ids(db, learner_id),
            # Recent failures outrank new material: each becomes a recursive drill ladder.
            struggling=tutor_store.struggling(db, learner_id),
        ),
        ctx,
    )
    return LessonOut(
        review=lesson.review,
        new=lesson.new,
        difficulty=lesson.difficulty,
        remediation=_steps_out(lesson.remediation),
    )


@router.post("/learner/{learner_id}/review", response_model=ReviewOut)
def learner_review(learner_id: int, payload: ReviewSubmit, db: Session = Depends(get_db)) -> ReviewOut:
    if tutor_store.get_learner(db, learner_id) is None:
        raise HTTPException(404, "unknown learner")
    rs = tutor_store.record_review(db, learner_id, payload.sign_id, payload.rating)
    return ReviewOut(
        sign_id=rs.sign_id,
        due=rs.due.isoformat(),
        stability=rs.stability,
        difficulty=rs.difficulty,
        reps=rs.reps,
        lapses=rs.lapses,
        state=rs.state,
    )


def _score_and_critique(learner: np.ndarray, reference: np.ndarray, language: str) -> ScoreOut:
    result = score_attempt(learner, reference)
    critique = _critique.run(result, AgentContext(language=language))
    return ScoreOut(
        overall=result.overall,
        parameters=result.parameters.__dict__,
        feedback_target=result.feedback_target,
        feedback_message=critique.message,
        passed=critique.passed,
    )


@router.post("/score", response_model=ScoreOut)
def score(payload: ScoreIn) -> ScoreOut:
    learner = np.asarray(payload.learner, dtype=np.float32)
    reference = np.asarray(payload.reference, dtype=np.float32)
    for name, arr in (("learner", learner), ("reference", reference)):
        if arr.ndim != 2 or arr.shape[1] != FEATURE_DIM:
            raise HTTPException(
                status_code=422,
                detail=f"{name} must be (frames, {FEATURE_DIM}); got {arr.shape}",
            )
    return _score_and_critique(learner, reference, payload.language)


class ScoreSignIn(BaseModel):
    sign_id: str
    learner: list[list[float]]
    language: str = "en"


@router.get("/score/status")
def score_status() -> dict:
    return {"references_available": references.available()}


@router.post("/score-sign", response_model=ScoreOut)
def score_sign(payload: ScoreSignIn) -> ScoreOut:
    """Score a learner attempt against the stored reference for a sign (DTW + Critique)."""
    ref = references.load_reference(payload.sign_id)
    if ref is None:
        raise HTTPException(404, f"no reference for {payload.sign_id} — run build_references.py")
    learner = np.asarray(payload.learner, dtype=np.float32)
    if learner.ndim != 2 or learner.shape[1] != FEATURE_DIM:
        raise HTTPException(422, f"learner must be (frames, {FEATURE_DIM}); got {learner.shape}")
    return _score_and_critique(learner, ref, payload.language)


class LearnerAttemptIn(BaseModel):
    sign_id: str
    learner: list[list[float]]


class LearnerAttemptOut(BaseModel):
    score: ScoreOut
    remediation: RemediationOut | None = None


@router.post("/learner/{learner_id}/attempt", response_model=LearnerAttemptOut)
def learner_attempt(
    learner_id: int, payload: LearnerAttemptIn, db: Session = Depends(get_db)
) -> LearnerAttemptOut:
    """Score an attempt, record it, and — if it failed — return the drill ladder.

    This is the endpoint that makes the tutor loop recursive: the attempt is persisted, so
    the next lesson knows what the learner is struggling with, and a failure comes back
    with the descent already computed rather than a bare percentage.
    """
    learner = tutor_store.get_learner(db, learner_id)
    if learner is None:
        raise HTTPException(404, "unknown learner")
    ref = references.load_reference(payload.sign_id)
    if ref is None:
        raise HTTPException(404, f"no reference for {payload.sign_id} — run build_references.py")
    attempt = np.asarray(payload.learner, dtype=np.float32)
    if attempt.ndim != 2 or attempt.shape[1] != FEATURE_DIM:
        raise HTTPException(422, f"learner must be (frames, {FEATURE_DIM}); got {attempt.shape}")

    scored = _score_and_critique(attempt, ref, learner.language)
    tutor_store.record_attempt(
        db, learner_id, payload.sign_id, scored.overall, scored.feedback_target
    )
    if scored.passed:
        return LearnerAttemptOut(score=scored)

    state = tutor_store.learner_state(db, learner)
    ctx = AgentContext(language=learner.language, mastery=state["mastery"])
    plan = RemediationAgent(_dictionary()).run(
        RemediationRequest(payload.sign_id, scored.feedback_target, scored.overall), ctx
    )
    return LearnerAttemptOut(score=scored, remediation=_plan_out(plan))


@router.get("/learner/{learner_id}/remediation", response_model=RemediationOut)
def learner_remediation(
    learner_id: int,
    sign_id: str,
    failed_parameter: str | None = None,
    db: Session = Depends(get_db),
) -> RemediationOut:
    """The drill ladder for a sign, using the learner's stored mastery.

    ``failed_parameter`` defaults to whatever the learner's most recent attempt at this
    sign got wrong.
    """
    learner = tutor_store.get_learner(db, learner_id)
    if learner is None:
        raise HTTPException(404, "unknown learner")
    if failed_parameter is None:
        recent = dict(tutor_store.struggling(db, learner_id, limit=50))
        failed_parameter = recent.get(sign_id, "handshape")
    state = tutor_store.learner_state(db, learner)
    ctx = AgentContext(language=learner.language, mastery=state["mastery"])
    try:
        plan = RemediationAgent(_dictionary()).run(
            RemediationRequest(sign_id, failed_parameter), ctx
        )
    except KeyError:
        raise HTTPException(404, f"unknown sign {sign_id}") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _plan_out(plan)


@router.post("/score-demo", response_model=ScoreOut)
def score_demo(sign_id: str, language: str = "en", noise: float = 0.12) -> ScoreOut:
    """Synthesize an attempt for a sign and score it — exercises the full DTW + Critique
    path without a webcam. Raise `noise` to see the score drop and the feedback change."""
    ref = references.load_reference(sign_id)
    if ref is None:
        raise HTTPException(404, f"no reference for {sign_id} — run build_references.py")
    attempt = references.synthesize_attempt(ref, noise)
    return _score_and_critique(attempt, ref, language)
