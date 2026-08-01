"""Animation Director agent — gloss sequence -> avatar clip plan.

Not language-aware (operates on sign IDs / gloss codes). Turns a sequence of signs into a
timed clip playlist with a co-articulation crossfade and a facial track derived from each
sign's non-manual markers. The three.js player consumes this plan (TECH_STACK.md Layer 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schema import SignDictionary
from .base import AgentContext

# Co-articulation window between clips (TECH_STACK.md: ~150-250ms crossfade).
DEFAULT_CLIP_MS = 900
CROSSFADE_MS = 200


@dataclass
class AnimationStep:
    sign_id: str
    clip_ref: str | None
    start_ms: int
    duration_ms: int
    crossfade_ms: int
    facial: dict[str, str] = field(default_factory=dict)  # NMM -> avatar face track


@dataclass
class AnimationPlan:
    steps: list[AnimationStep]
    total_ms: int


class AnimationDirectorAgent:
    name = "animation_director"
    language_aware = False

    def __init__(self, dictionary: SignDictionary):
        self.dictionary = dictionary
        self._by_gloss = {s.gloss_code: s for s in dictionary.signs}

    def _resolve(self, token: str):
        # Accept either a sign_id (NSL_dddd) or a gloss_code.
        try:
            return self.dictionary.by_id(token)
        except KeyError:
            return self._by_gloss.get(token)

    def run(self, gloss_sequence: list[str], ctx: AgentContext) -> AnimationPlan:
        steps: list[AnimationStep] = []
        cursor = 0
        for i, token in enumerate(gloss_sequence):
            sign = self._resolve(token)
            facial = {}
            if sign and sign.non_manual_markers:
                facial = sign.non_manual_markers.model_dump(exclude_none=True)
            crossfade = CROSSFADE_MS if i > 0 else 0
            start = max(cursor - crossfade, 0)
            steps.append(
                AnimationStep(
                    sign_id=sign.sign_id if sign else token,
                    clip_ref=sign.clip_ref if sign else None,
                    start_ms=start,
                    duration_ms=DEFAULT_CLIP_MS,
                    crossfade_ms=crossfade,
                    facial=facial,
                )
            )
            cursor = start + DEFAULT_CLIP_MS
        return AnimationPlan(steps=steps, total_ms=cursor)
