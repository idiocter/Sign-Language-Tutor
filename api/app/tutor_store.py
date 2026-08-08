"""Persistence for the tutor loop: learners, FSRS review state, attempts, streaks.

Bridges the SQLAlchemy models with the stateless scheduler in signbridge.tutor. Mastery and
streaks are derived here so the API stays thin.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from signbridge.tutor.calendar_bs import to_bs_string
from signbridge.tutor.scheduler import Rating, ReviewCard, Scheduler

from .models import Attempt, Learner, ReviewState

_scheduler = Scheduler()


def _naive_utc(dt: datetime) -> datetime:
    """Strip tzinfo (SQLite stores naive), converting aware datetimes to UTC first."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def create_learner(db: Session, display_name: str, language: str) -> Learner:
    learner = Learner(display_name=display_name or "Learner", language=language or "en")
    db.add(learner)
    db.commit()
    db.refresh(learner)
    return learner


def get_learner(db: Session, learner_id: int) -> Learner | None:
    return db.get(Learner, learner_id)


def _reviews(db: Session, learner_id: int) -> list[ReviewState]:
    return list(db.scalars(select(ReviewState).where(ReviewState.learner_id == learner_id)))


def _to_card(rs: ReviewState) -> ReviewCard:
    return ReviewCard(
        sign_id=rs.sign_id,
        due=rs.due,
        stability=rs.stability,
        difficulty=rs.difficulty,
        reps=rs.reps,
        lapses=rs.lapses,
        state=rs.state,
    )


def mastery_map(reviews: list[ReviewState]) -> dict[str, float]:
    """0..1 per sign. Reaches the 0.8 'mastered' bar the Curriculum agent uses at ~4 reps."""
    out: dict[str, float] = {}
    for r in reviews:
        base = min(1.0, r.reps / 5.0)
        if r.state in {"new", "learning", "relearning"}:
            base = min(base, 0.5)
        out[r.sign_id] = round(base, 3)
    return out


def due_sign_ids(db: Session, learner_id: int, now: datetime | None = None) -> list[str]:
    now = _naive_utc(now or datetime.now(timezone.utc))
    reviews = _reviews(db, learner_id)
    due = [r for r in reviews if _naive_utc(r.due) <= now and r.state != "new"]
    due.sort(key=lambda r: r.due)
    return [r.sign_id for r in due]


def record_review(db: Session, learner_id: int, sign_id: str, rating: int) -> ReviewState:
    rs = db.scalar(
        select(ReviewState).where(
            ReviewState.learner_id == learner_id, ReviewState.sign_id == sign_id
        )
    )
    if rs is None:
        # Set defaults explicitly — column defaults only apply at INSERT, but we read the
        # card fields before that.
        rs = ReviewState(
            learner_id=learner_id,
            sign_id=sign_id,
            state="new",
            due=datetime.now(timezone.utc),
            stability=0.0,
            difficulty=0.0,
            reps=0,
            lapses=0,
        )
        db.add(rs)

    updated = _scheduler.review(_to_card(rs), Rating(rating))
    rs.due = updated.due
    rs.stability = updated.stability
    rs.difficulty = updated.difficulty
    rs.reps = updated.reps
    rs.lapses = updated.lapses
    rs.state = updated.state
    rs.last_review = updated.last_review or datetime.now(timezone.utc)
    db.commit()
    db.refresh(rs)
    return rs


def record_attempt(db: Session, learner_id: int, sign_id: str, overall: float, target: str) -> None:
    db.add(
        Attempt(learner_id=learner_id, sign_id=sign_id, overall=overall, feedback_target=target)
    )
    db.commit()


def struggling(
    db: Session, learner_id: int, *, threshold: float = 80.0, limit: int = 3
) -> list[tuple[str, str]]:
    """Signs whose *most recent* attempt fell short, with the parameter that cost the most.

    Only the latest attempt per sign counts: a learner who failed a sign three times and
    then got it should not be dragged back through a drill ladder for it. Feeds
    ``LessonRequest.struggling``, which turns each pair into a recursive remediation plan.
    """
    attempts = db.scalars(
        select(Attempt)
        .where(Attempt.learner_id == learner_id)
        .order_by(Attempt.created_at.desc(), Attempt.id.desc())
    )
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for a in attempts:
        if a.sign_id in seen:
            continue
        seen.add(a.sign_id)
        if a.overall < threshold:
            out.append((a.sign_id, a.feedback_target))
        if len(out) >= limit:
            break
    return out


def current_streak(reviews: list[ReviewState], now: datetime | None = None) -> int:
    """Consecutive days (up to today) with at least one review. BS calendar is the display
    layer; day boundaries match Gregorian, so we count Gregorian days here."""
    now = now or datetime.now(timezone.utc)
    days = {r.last_review.date() for r in reviews if r.last_review}
    if not days:
        return 0
    streak = 0
    d = now.date()
    if d not in days:  # allow the streak to still count if the most recent activity was today-only
        d = max(days)
        if d < now.date() - timedelta(days=1):
            return 0
    while d in days:
        streak += 1
        d = d - timedelta(days=1)
    return streak


def learner_state(db: Session, learner: Learner) -> dict:
    reviews = _reviews(db, learner.id)
    now = datetime.now(timezone.utc)
    now_naive = _naive_utc(now)
    mastery = mastery_map(reviews)
    return {
        "id": learner.id,
        "display_name": learner.display_name,
        "language": learner.language,
        "mastery": mastery,
        "signs_started": len(reviews),
        "signs_mastered": sum(1 for v in mastery.values() if v >= 0.8),
        "due_count": len([r for r in reviews if _naive_utc(r.due) <= now_naive and r.state != "new"]),
        "streak": current_streak(reviews, now),
        "today_bs": to_bs_string(now.date()),
    }
