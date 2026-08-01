"""Curriculum agent — sequences the next lesson from mastery + schedule.

Not language-aware (it emits sign IDs, not text). Respects prerequisites and difficulty
from the sign dictionary, and prioritizes due reviews over new material.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schema import SignDictionary
from .base import AgentContext


@dataclass
class LessonRequest:
    lesson_size: int = 10
    due_sign_ids: list[str] = field(default_factory=list)  # from the scheduler


@dataclass
class Lesson:
    review: list[str]       # due sign_ids to revisit
    new: list[str]          # newly introduced sign_ids
    difficulty: int         # target difficulty of the new batch


class CurriculumAgent:
    name = "curriculum"
    language_aware = False

    def __init__(self, dictionary: SignDictionary):
        self.dictionary = dictionary

    def _unlocked(self, mastery: dict[str, float], threshold: float) -> set[str]:
        return {sid for sid, m in mastery.items() if m >= threshold}

    def run(self, payload: LessonRequest, ctx: AgentContext) -> Lesson:
        mastered = self._unlocked(ctx.mastery, threshold=0.8)
        review = payload.due_sign_ids[: payload.lesson_size]
        budget = max(payload.lesson_size - len(review), 0)

        # Candidates: not yet started, prerequisites satisfied. Easiest first.
        candidates = [
            s
            for s in self.dictionary.signs
            if s.sign_id not in ctx.mastery
            and all(p in mastered for p in s.curriculum.prerequisites)
        ]
        candidates.sort(key=lambda s: (s.curriculum.difficulty, s.sign_id))
        new = [s.sign_id for s in candidates[:budget]]
        target_diff = (
            max((self.dictionary.by_id(sid).curriculum.difficulty for sid in new), default=1)
        )
        return Lesson(review=review, new=new, difficulty=target_diff)
