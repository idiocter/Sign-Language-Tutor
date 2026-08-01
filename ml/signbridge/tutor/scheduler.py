"""Spaced-repetition scheduling for sign review.

TECH_STACK.md Layer 6 picks **FSRS** (better retention than SM-2). This wraps the
``fsrs`` package (py-fsrs) behind a stable, backend-agnostic interface so the rest of the
app deals in ``ReviewCard`` + a rating, never the library's evolving API.

If ``fsrs`` is not installed (or its API doesn't match a version we know), a small,
clearly-labelled interval fallback is used so the tutor loop still runs. The fallback is
not FSRS — it just keeps intervals monotonic in rating (Easy > Good > Hard > Again) so
the scheduler is always usable in development.

Dates are handled as timezone-aware UTC datetimes. The Bikram Sambat calendar
(``nepali-datetime``) is applied only at the *presentation* layer for streaks and
schedules — never in the scheduling math. See :mod:`signbridge.tutor.calendar_bs`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum


class Rating(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


@dataclass
class ReviewCard:
    """One learnable sign's review state for one learner."""

    sign_id: str
    due: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stability: float = 0.0
    difficulty: float = 0.0
    reps: int = 0
    lapses: int = 0
    last_review: datetime | None = None
    state: str = "new"  # new | learning | review | relearning


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Scheduler:
    """Schedules the next review for a card given the learner's rating."""

    def __init__(self, requested_retention: float = 0.9):
        self.requested_retention = requested_retention
        self._backend, self._impl = self._init_backend(requested_retention)

    @staticmethod
    def _init_backend(retention: float):
        """Detect a usable py-fsrs API; fall back to the interval heuristic."""
        try:
            import fsrs  # noqa: F401

            # py-fsrs >= 5: Scheduler(...).review_card(card, rating)
            if hasattr(fsrs, "Scheduler") and hasattr(fsrs, "Card"):
                sched = fsrs.Scheduler(desired_retention=retention)
                return "fsrs.Scheduler", sched
            # py-fsrs 4.x: FSRS().repeat(card, now)[rating]
            if hasattr(fsrs, "FSRS"):
                return "fsrs.FSRS", fsrs.FSRS()
        except Exception:
            pass
        return "fallback", None

    # --- public API ---------------------------------------------------------

    def review(self, card: ReviewCard, rating: Rating, *, now: datetime | None = None) -> ReviewCard:
        now = now or _now()
        if self._backend == "fallback":
            return self._review_fallback(card, rating, now)
        return self._review_fsrs(card, rating, now)

    # --- fallback backend ---------------------------------------------------

    _BASE_DAYS = {Rating.AGAIN: 0.0, Rating.HARD: 1.0, Rating.GOOD: 3.0, Rating.EASY: 7.0}
    _GROWTH = {Rating.AGAIN: 0.0, Rating.HARD: 1.2, Rating.GOOD: 2.5, Rating.EASY: 3.5}

    def _review_fallback(self, card: ReviewCard, rating: Rating, now: datetime) -> ReviewCard:
        reps = 0 if rating == Rating.AGAIN else card.reps + 1
        lapses = card.lapses + (1 if rating == Rating.AGAIN and card.state == "review" else 0)
        prev = max(card.stability, self._BASE_DAYS[Rating.HARD])
        if rating == Rating.AGAIN:
            interval_days = 0.007  # ~10 min relearn step
            state = "relearning" if card.state == "review" else "learning"
        else:
            interval_days = self._BASE_DAYS[rating] * (self._GROWTH[rating] ** max(reps - 1, 0))
            interval_days = min(interval_days, 365.0)
            interval_days = max(interval_days, prev * 0.5) if card.state == "review" else interval_days
            state = "review"
        return ReviewCard(
            sign_id=card.sign_id,
            due=now + timedelta(days=interval_days),
            stability=interval_days,
            difficulty=card.difficulty,
            reps=reps,
            lapses=lapses,
            last_review=now,
            state=state,
        )

    # --- py-fsrs backends ---------------------------------------------------

    def _review_fsrs(self, card: ReviewCard, rating: Rating, now: datetime) -> ReviewCard:
        import fsrs

        rating_enum = self._map_rating(fsrs, rating)
        if self._backend == "fsrs.Scheduler":
            fcard = self._to_fsrs_card(fsrs, card)
            new_fcard, _log = self._impl.review_card(fcard, rating_enum, now)
        else:  # fsrs.FSRS (4.x)
            fcard = self._to_fsrs_card(fsrs, card)
            scheduling = self._impl.repeat(fcard, now)
            new_fcard = scheduling[rating_enum].card
        return self._from_fsrs_card(card, rating, new_fcard, now)

    @staticmethod
    def _map_rating(fsrs, rating: Rating):
        return {
            Rating.AGAIN: fsrs.Rating.Again,
            Rating.HARD: fsrs.Rating.Hard,
            Rating.GOOD: fsrs.Rating.Good,
            Rating.EASY: fsrs.Rating.Easy,
        }[rating]

    @staticmethod
    def _to_fsrs_card(fsrs, card: ReviewCard):
        fcard = fsrs.Card()
        if card.state != "new":
            # Best-effort carry-over; py-fsrs recomputes internal fields on review.
            if hasattr(fcard, "stability"):
                fcard.stability = card.stability or None
            if hasattr(fcard, "difficulty"):
                fcard.difficulty = card.difficulty or None
            if hasattr(fcard, "due"):
                fcard.due = card.due
        return fcard

    def _from_fsrs_card(self, prev: ReviewCard, rating: Rating, fcard, now: datetime) -> ReviewCard:
        # Take scheduling numbers (due/stability/difficulty) from py-fsrs, but track
        # reps/lapses/state ourselves — those fields differ across py-fsrs versions.
        reps = 0 if rating == Rating.AGAIN else prev.reps + 1
        lapses = prev.lapses + (1 if rating == Rating.AGAIN and prev.state == "review" else 0)
        if rating == Rating.AGAIN:
            state = "relearning" if prev.state == "review" else "learning"
        else:
            state = "review" if prev.state in {"review", "learning"} else "learning"
        return ReviewCard(
            sign_id=prev.sign_id,
            due=getattr(fcard, "due", now),
            stability=float(getattr(fcard, "stability", 0.0) or 0.0),
            difficulty=float(getattr(fcard, "difficulty", 0.0) or 0.0),
            reps=reps,
            lapses=lapses,
            last_review=now,
            state=state,
        )


def due_cards(cards: list[ReviewCard], *, now: datetime | None = None) -> list[ReviewCard]:
    """Cards whose review is due, soonest first."""
    now = now or _now()
    return sorted((c for c in cards if c.due <= now), key=lambda c: c.due)
