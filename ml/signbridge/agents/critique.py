"""Critique agent — turns a per-parameter DTW score into a specific correction.

Language-aware. Nepali feedback uses slot-filled templates (reliable, no hallucination);
English can go through an LLM for more natural phrasing but falls back to the same
templates. The point (TECH_STACK.md Layer 6): "handshape correct, movement amplitude too
small" is a lesson; "72% match" is not.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..scoring.dtw import ScoreResult
from .base import AgentContext

# Slot-filled feedback per (parameter, language). Concrete and reviewable — deaf advisors
# should sign off on the Nepali wording before launch.
_TEMPLATES: dict[str, dict[str, str]] = {
    "handshape": {
        "en": "Your hand shape drifted. Match the reference finger positions more closely.",
        "ne": "तपाईंको हातको आकार मिलेन। औंलाको स्थिति नमुनासँग मिलाउनुहोस्।",
    },
    "location": {
        "en": "The sign is in the wrong place. Move your hands to the correct location on your body.",
        "ne": "चिन्ह गलत ठाउँमा छ। हातलाई शरीरको सही स्थानमा लैजानुहोस्।",
    },
    "movement": {
        "en": "The movement was off — check the path and its amplitude.",
        "ne": "चाल मिलेन — चालको बाटो र आकार जाँच गर्नुहोस्।",
    },
    "orientation": {
        "en": "Your palm is facing the wrong way. Rotate to match the reference orientation.",
        "ne": "तपाईंको हत्केला गलत दिशामा छ। नमुनाअनुसार घुमाउनुहोस्।",
    },
}
_PRAISE = {
    "en": "Well done — that was a strong match. Keep it up!",
    "ne": "राम्रो! धेरै मिल्दो थियो। यसै गर्दै जानुहोस्!",
}


@dataclass
class Critique:
    target: str          # parameter to correct first
    message: str         # localized, learner-facing
    score: float         # 0..100
    passed: bool


class CritiqueAgent:
    name = "critique"
    language_aware = True

    def __init__(self, pass_threshold: float = 80.0):
        self.pass_threshold = pass_threshold

    def run(self, payload: ScoreResult, ctx: AgentContext) -> Critique:
        lang = ctx.language
        passed = payload.overall >= self.pass_threshold
        if passed:
            msg = _PRAISE[lang]
        else:
            msg = _TEMPLATES[payload.feedback_target][lang]
        return Critique(
            target=payload.feedback_target,
            message=msg,
            score=payload.overall,
            passed=passed,
        )
