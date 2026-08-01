"""Tutor endpoints: lesson sequencing, spaced-repetition review, movement scoring."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from signbridge.agents.base import AgentContext
from signbridge.agents.critique import CritiqueAgent
from signbridge.agents.curriculum import CurriculumAgent, LessonRequest
from signbridge.config import FEATURE_DIM
from signbridge.scoring.dtw import score_attempt
from signbridge.tutor.scheduler import Rating, ReviewCard, Scheduler

from ..schemas import (
    LessonIn,
    LessonOut,
    ReviewIn,
    ReviewOut,
    ScoreIn,
    ScoreOut,
)
from .signs import _dictionary

router = APIRouter(prefix="/tutor", tags=["tutor"])

_scheduler = Scheduler()
_critique = CritiqueAgent()


@router.post("/lesson", response_model=LessonOut)
def next_lesson(payload: LessonIn) -> LessonOut:
    agent = CurriculumAgent(_dictionary())
    ctx = AgentContext(language=payload.language, mastery=payload.mastery)
    lesson = agent.run(
        LessonRequest(lesson_size=payload.lesson_size, due_sign_ids=payload.due_sign_ids),
        ctx,
    )
    return LessonOut(review=lesson.review, new=lesson.new, difficulty=lesson.difficulty)


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
    result = score_attempt(learner, reference)
    critique = _critique.run(result, AgentContext(language=payload.language))
    return ScoreOut(
        overall=result.overall,
        parameters=result.parameters.__dict__,
        feedback_target=result.feedback_target,
        feedback_message=critique.message,
        passed=critique.passed,
    )
