"""Pydantic request/response models for the API surface."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Signs / vocabulary -----------------------------------------------------

class SignOut(BaseModel):
    sign_id: str
    en: str
    ne: str
    ne_roman: str | None = None
    gloss_code: str
    category: str | None = None
    difficulty: int
    clip_ref: str | None = None


class TransliterateIn(BaseModel):
    text: str = Field(..., examples=["namaste"])


class TransliterateOut(BaseModel):
    input: str
    devanagari: str


# --- Tutor ------------------------------------------------------------------

class LessonIn(BaseModel):
    language: str = "en"
    lesson_size: int = 10
    mastery: dict[str, float] = Field(default_factory=dict)
    due_sign_ids: list[str] = Field(default_factory=list)


class LessonOut(BaseModel):
    review: list[str]
    new: list[str]
    difficulty: int


class ReviewIn(BaseModel):
    sign_id: str
    rating: int = Field(..., ge=1, le=4, description="1=Again 2=Hard 3=Good 4=Easy")
    stability: float = 0.0
    difficulty: float = 0.0
    reps: int = 0
    lapses: int = 0
    state: str = "new"


class ReviewOut(BaseModel):
    sign_id: str
    due: str            # ISO timestamp
    stability: float
    difficulty: float
    reps: int
    lapses: int
    state: str


class ScoreIn(BaseModel):
    language: str = "en"
    learner: list[list[float]] = Field(..., description="(frames, FEATURE_DIM) landmarks")
    reference: list[list[float]] = Field(..., description="(frames, FEATURE_DIM) landmarks")


class ScoreOut(BaseModel):
    overall: float
    parameters: dict[str, float]
    feedback_target: str
    feedback_message: str
    passed: bool
