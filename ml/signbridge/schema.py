"""Typed loader and validator for the sign dictionary.

Mirrors ``data/sign_schema.json`` (the JSON-Schema contract) as pydantic models so the
rest of the codebase works with validated, autocompleted objects instead of raw dicts.

The golden rule from the schema file: **signs are keyed by language-neutral IDs**
(``NSL_0001``), never by English words. ``sign_id`` is the only key that crosses models,
clips, and agents.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .config import DICTIONARY_PATH

SIGN_ID_RE = re.compile(r"^NSL_[0-9]{4}$")


class Labels(BaseModel):
    en: str
    ne: str  # Devanagari
    ne_roman: str | None = None  # Romanized, for search / transliteration fallback


class Parameters(BaseModel):
    """Sign phonology — drives DTW error decomposition and learner feedback."""

    handshape: str
    location: str
    movement: str
    orientation: str
    two_handed: bool = False
    symmetric: bool = False


class NonManualMarkers(BaseModel):
    """Facial grammar. Maps to ARKit blendshapes on the avatar."""

    eyebrows: Literal["raised", "furrowed", "neutral"] | None = None
    mouth_morpheme: str | None = None
    head: Literal["tilt_forward", "tilt_back", "shake", "nod", "neutral"] | None = None
    eye_gaze: str | None = None


class Curriculum(BaseModel):
    difficulty: int = Field(default=1, ge=1, le=5)
    prerequisites: list[str] = Field(default_factory=list)
    category: str | None = None
    phase: int | None = None


class Sign(BaseModel):
    sign_id: str
    labels: Labels
    gloss_code: str
    parameters: Parameters
    non_manual_markers: NonManualMarkers | None = None
    clip_ref: str | None = None
    reference_landmarks: str | None = None
    curriculum: Curriculum = Field(default_factory=Curriculum)
    samples_collected: int = 0
    signers_recorded: int = 0  # need 5+ distinct signers per sign
    validated_by_native_signer: bool = False

    @field_validator("sign_id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not SIGN_ID_RE.match(v):
            raise ValueError(f"sign_id must match NSL_dddd, got {v!r}")
        return v


class SignDictionary(BaseModel):
    version: str = "0.1.0"
    sign_language: Literal["NSL"] = "NSL"
    signs: list[Sign] = Field(default_factory=list)

    def by_id(self, sign_id: str) -> Sign:
        for s in self.signs:
            if s.sign_id == sign_id:
                return s
        raise KeyError(sign_id)

    def ready_for_training(self, min_signers: int = 5) -> list[Sign]:
        """Signs with enough distinct signers to survive a signer-split (see plan)."""
        return [s for s in self.signs if s.signers_recorded >= min_signers]


def load_dictionary(path: Path | str = DICTIONARY_PATH) -> SignDictionary:
    """Load and validate the sign dictionary JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return SignDictionary.model_validate(data)


def save_dictionary(d: SignDictionary, path: Path | str = DICTIONARY_PATH) -> None:
    Path(path).write_text(
        json.dumps(d.model_dump(exclude_none=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
