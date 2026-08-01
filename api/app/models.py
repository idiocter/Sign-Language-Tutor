"""SQLAlchemy models — learners, per-sign review state, scored attempts.

Kept intentionally small. pgvector-backed embedding search (for nearest-sign lookup and
dedupe) is a Phase 4 concern and lives behind Postgres; not modelled here yet.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(2), default="en")  # en | ne
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    reviews: Mapped[list["ReviewState"]] = relationship(back_populates="learner")


class ReviewState(Base):
    """One learner's FSRS state for one sign (mirrors tutor.scheduler.ReviewCard)."""

    __tablename__ = "review_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    sign_id: Mapped[str] = mapped_column(String(16), index=True)  # NSL_dddd
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(16), default="new")

    learner: Mapped[Learner] = relationship(back_populates="reviews")


class Attempt(Base):
    """A scored practice attempt — the score decomposition, not the raw landmarks."""

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("learners.id"), index=True)
    sign_id: Mapped[str] = mapped_column(String(16), index=True)
    overall: Mapped[float] = mapped_column(Float)
    feedback_target: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
