"""Curriculum agent — sequences the next lesson from mastery + schedule.

Not language-aware (it emits sign IDs, not text). Respects prerequisites and difficulty
from the sign dictionary, and prioritizes due reviews over new material.

When the caller reports signs the learner is *struggling* with, the lesson also carries a
remediation ladder built by :class:`~signbridge.agents.remediation.RemediationAgent`,
which recurses down the phonological-component graph until it reaches something the
learner has already mastered. Piling on more new signs is the wrong answer to a failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schema import SignDictionary
from .base import AgentContext
from .remediation import DrillStep, RemediationAgent, RemediationRequest


@dataclass
class LessonRequest:
    lesson_size: int = 10
    due_sign_ids: list[str] = field(default_factory=list)  # from the scheduler
    # (sign_id, failed_parameter) pairs from recent low-scoring attempts. Each one gets a
    # recursive drill ladder instead of simply being re-queued.
    struggling: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Lesson:
    review: list[str]       # due sign_ids to revisit
    new: list[str]          # newly introduced sign_ids
    difficulty: int         # target difficulty of the new batch
    remediation: list[DrillStep] = field(default_factory=list)  # foundation-first drills


class CurriculumAgent:
    name = "curriculum"
    language_aware = False

    def __init__(self, dictionary: SignDictionary):
        self.dictionary = dictionary
        self._remediation = RemediationAgent(dictionary)

    def _unlocked(self, mastery: dict[str, float], threshold: float) -> set[str]:
        return {sid for sid, m in mastery.items() if m >= threshold}

    def _remediate(self, payload: LessonRequest, ctx: AgentContext) -> list[DrillStep]:
        steps: list[DrillStep] = []
        for sign_id, parameter in payload.struggling:
            try:
                plan = self._remediation.run(RemediationRequest(sign_id, parameter), ctx)
            except (KeyError, ValueError):
                continue  # unknown sign or parameter — skip rather than fail the lesson
            steps.extend(plan.steps)
        return steps

    def run(self, payload: LessonRequest, ctx: AgentContext) -> Lesson:
        mastered = self._unlocked(ctx.mastery, threshold=0.8)
        remediation = self._remediate(payload, ctx)
        review = payload.due_sign_ids[: payload.lesson_size]
        # A struggling sign is already covered by its drill ladder; don't also queue it raw.
        struggling_ids = {sign_id for sign_id, _ in payload.struggling}
        review = [sid for sid in review if sid not in struggling_ids]
        # Remediation is the lesson's real work — new material yields to it.
        budget = max(payload.lesson_size - len(review) - len(struggling_ids), 0)

        # Candidates: not yet started, prerequisites satisfied. Easiest first.
        candidates = [
            s
            for s in self.dictionary.signs
            if s.sign_id not in ctx.mastery
            and s.sign_id not in struggling_ids  # already the subject of a drill ladder
            and all(p in mastered for p in s.curriculum.prerequisites)
        ]
        candidates.sort(key=lambda s: (s.curriculum.difficulty, s.sign_id))
        new = [s.sign_id for s in candidates[:budget]]
        target_diff = (
            max((self.dictionary.by_id(sid).curriculum.difficulty for sid in new), default=1)
        )
        return Lesson(review=review, new=new, difficulty=target_diff, remediation=remediation)
