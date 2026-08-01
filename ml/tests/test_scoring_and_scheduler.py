"""DTW scoring decomposition and the spaced-repetition scheduler interface."""

from __future__ import annotations

import numpy as np

from signbridge.agents.base import AgentContext
from signbridge.agents.critique import CritiqueAgent
from signbridge.config import FEATURE_DIM, SEQ_LEN
from signbridge.scoring.dtw import score_attempt
from signbridge.tutor.scheduler import Rating, ReviewCard, Scheduler


def _seq(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(SEQ_LEN, FEATURE_DIM)).astype(np.float32)


def test_identical_attempt_scores_high():
    ref = _seq(3)
    result = score_attempt(ref.copy(), ref)
    assert result.overall > 95.0
    assert result.overall <= 100.0


def test_different_attempt_scores_lower_than_identical():
    ref = _seq(3)
    good = score_attempt(ref.copy(), ref).overall
    bad = score_attempt(_seq(99), ref).overall
    assert bad < good


def test_score_reports_a_parameter_target():
    res = score_attempt(_seq(1), _seq(2))
    assert res.feedback_target in {"handshape", "location", "movement", "orientation"}


def test_critique_agent_localizes():
    res = score_attempt(_seq(1), _seq(2))
    en = CritiqueAgent().run(res, AgentContext(language="en"))
    ne = CritiqueAgent().run(res, AgentContext(language="ne"))
    assert en.message and ne.message and en.message != ne.message


def test_scheduler_intervals_monotonic_in_rating():
    sched = Scheduler()
    base = ReviewCard(sign_id="NSL_0001")
    again = sched.review(base, Rating.AGAIN)
    good = sched.review(base, Rating.GOOD)
    easy = sched.review(base, Rating.EASY)
    assert again.due <= good.due <= easy.due


def test_scheduler_advances_due_date():
    sched = Scheduler()
    card = ReviewCard(sign_id="NSL_0002")
    reviewed = sched.review(card, Rating.GOOD)
    assert reviewed.due > card.due
    assert reviewed.reps == 1
