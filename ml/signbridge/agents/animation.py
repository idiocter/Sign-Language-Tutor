"""Animation Director agent — gloss sequence -> avatar clip plan.

Not language-aware (operates on sign IDs / gloss codes). Turns a sequence of signs into a
timed clip playlist with a co-articulation crossfade, a **procedural pose** derived from
each sign's phonology, and a **facial track** in ARKit blendshape space derived from its
non-manual markers. The three.js player consumes this plan (TECH_STACK.md Layer 3).

If a sign has an authored glTF clip (`clip_ref` resolves to a real `.glb`), the player uses
it and ignores the procedural pose. Until clips are authored, the procedural pose drives
every sign so the pipeline is demonstrable end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..facial import track_for
from ..posing import pose_for
from ..schema import SignDictionary
from .base import AgentContext

# Co-articulation window between clips (TECH_STACK.md: ~150-250ms crossfade).
DEFAULT_CLIP_MS = 900
CROSSFADE_MS = 200


@dataclass
class AnimationStep:
    sign_id: str
    gloss: str
    clip_ref: str | None
    start_ms: int
    duration_ms: int
    crossfade_ms: int
    pose: dict | None = None      # procedural pose spec (posing.pose_for)
    facial: dict = field(default_factory=dict)  # ARKit facial track (facial.track_for)


@dataclass
class AnimationPlan:
    steps: list[AnimationStep]
    total_ms: int

    def has_facial_motion(self) -> bool:
        """Phase 2 exit gate: the face must not be static across the whole plan."""
        return any(not s.facial.get("static", True) for s in self.steps)


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
            crossfade = CROSSFADE_MS if i > 0 else 0
            start = max(cursor - crossfade, 0)
            if sign is not None:
                pose = pose_for(sign.parameters)
                facial = track_for(sign.non_manual_markers)
                steps.append(
                    AnimationStep(
                        sign_id=sign.sign_id,
                        gloss=sign.gloss_code,
                        clip_ref=sign.clip_ref,
                        start_ms=start,
                        duration_ms=DEFAULT_CLIP_MS,
                        crossfade_ms=crossfade,
                        pose=pose,
                        facial=facial,
                    )
                )
            else:
                # Unknown token (e.g. fingerspelling) — hold a neutral beat.
                steps.append(
                    AnimationStep(
                        sign_id=token,
                        gloss=token,
                        clip_ref=None,
                        start_ms=start,
                        duration_ms=DEFAULT_CLIP_MS,
                        crossfade_ms=crossfade,
                        pose=None,
                        facial=track_for(None),
                    )
                )
            cursor = start + DEFAULT_CLIP_MS
        return AnimationPlan(steps=steps, total_ms=cursor)
