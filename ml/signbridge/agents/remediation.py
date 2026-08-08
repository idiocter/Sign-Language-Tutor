"""Remediation agent — recursive curriculum descent.

:class:`~signbridge.agents.curriculum.CurriculumAgent` answers "what next?". This answers
the harder question a tutor faces the moment a learner fails a sign: **what is this sign
built out of, and how far down do I have to go before I reach something they can already
do?**

The dictionary exposes two structures worth recursing over:

* ``curriculum.prerequisites`` — explicit ordering (often empty in the seed vocabulary).
* ``parameters`` — the phonology. Signs sharing a handshape / location / movement /
  orientation value are neighbours in a component graph, and an *easier* neighbour the
  learner has already mastered is a foundation they can rebuild the failed sign from.

The agent walks that graph depth-first from the failed sign, descending until it reaches
mastered material or a depth cap, then emits the drills **foundation-first**: the learner
restarts from the deepest thing they can already do and re-ascends to the sign they
missed. Revisits and cycles are impossible by construction (a ``visited`` set), and the
plan length is capped, so a densely-connected dictionary can never produce an endless
lesson.

Symbolic only — steps carry sign IDs and parameter names, never landmarks. Language-aware
only for the learner-facing ``instruction``, which is slot-filled from templates. As with
:mod:`signbridge.agents.critique`, deaf advisors must sign off on the Nepali wording
before launch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..schema import Sign, SignDictionary
from .base import AgentContext

# The four phonological parameters DTW scoring decomposes error into. Keeping this tuple
# aligned with scoring.dtw.ParameterErrors is what lets a score feed straight into a plan.
PARAMETERS = ("handshape", "location", "movement", "orientation")

# Same bar the Curriculum agent uses to unlock new material, so "mastered" means one thing.
MASTERY_THRESHOLD = 0.8

StepKind = Literal["foundation", "component", "sign", "target"]


# --- Localized drill text ---------------------------------------------------

_PARAM_LABEL = {
    "handshape": {"en": "handshape", "ne": "हातको आकार"},
    "location": {"en": "location", "ne": "स्थान"},
    "movement": {"en": "movement", "ne": "चाल"},
    "orientation": {"en": "palm orientation", "ne": "हत्केलाको दिशा"},
}

_COMPONENT_TEXT = {
    "handshape": {
        "en": "Hold the {value} handshape on its own — no movement, five slow repetitions.",
        "ne": "{value} हातको आकार मात्र बनाउनुहोस् — चाल नगरी, बिस्तारै पाँच पटक।",
    },
    "location": {
        "en": "Put your hands at {value} and hold. Fix the position before adding the sign.",
        "ne": "हात {value} मा राखेर स्थिर राख्नुहोस्। चिन्ह थप्नुअघि स्थान मिलाउनुहोस्।",
    },
    "movement": {
        "en": "Trace the {value} movement slowly with a relaxed hand, five times.",
        "ne": "{value} चाल हात खुकुलो पारेर बिस्तारै पाँच पटक दोहोर्‍याउनुहोस्।",
    },
    "orientation": {
        "en": "Turn your palm to {value} and hold it while you count to five.",
        "ne": "हत्केला {value} तर्फ फर्काएर पाँच गन्दासम्म स्थिर राख्नुहोस्।",
    },
}

_FOUNDATION_TEXT = {
    "en": "Start from {label}, which you already know — it uses the same {parameter}.",
    "ne": "तपाईंलाई आउने {label} बाट सुरु गर्नुहोस् — यसमा पनि उही {parameter} छ।",
}
_SIGN_TEXT = {
    "en": "Now build up: sign {label}. It shares the {parameter} you missed.",
    "ne": "अब {label} संकेत गर्नुहोस्। यसमा तपाईंले चुकाउनुभएको {parameter} छ।",
}
_PREREQ_TEXT = {
    "en": "{label} comes first — it is a prerequisite for the sign you are working on.",
    "ne": "पहिले {label} — तपाईंले अभ्यास गरिरहेको चिन्हको पूर्वशर्त हो।",
}
_TARGET_TEXT = {
    "en": "Back to {label}. Watch the {parameter} this time.",
    "ne": "अब फेरि {label}। यसपटक {parameter}मा ध्यान दिनुहोस्।",
}


# --- Types ------------------------------------------------------------------

@dataclass
class DrillStep:
    """One rung of the ladder. ``depth`` 0 is the sign the learner actually failed."""

    kind: StepKind
    depth: int
    instruction: str            # localized, learner-facing
    sign_id: str | None = None
    parameter: str | None = None
    component_value: str | None = None   # e.g. "flat_B" for a handshape drill
    reference_sign_id: str | None = None  # a sign the avatar can demo the component with
    reason: str = ""            # why this step is here (symbolic, for logs/UI)


@dataclass
class RemediationRequest:
    sign_id: str
    failed_parameter: str = "handshape"   # ScoreResult.feedback_target
    score: float | None = None            # 0..100, informational


@dataclass
class RemediationPlan:
    target_sign_id: str
    failed_parameter: str
    steps: list[DrillStep] = field(default_factory=list)
    depth_reached: int = 0
    truncated: bool = False   # a cap stopped the descent before it hit mastered material

    def sign_sequence(self) -> list[str]:
        """Sign IDs to practice, in order, skipping pure component drills."""
        return [s.sign_id for s in self.steps if s.sign_id and s.kind != "component"]


# --- Agent ------------------------------------------------------------------

class RemediationAgent:
    """Recursive descent over the prerequisite + phonological-component graph.

    Extends the Curriculum agent's role rather than adding a new Layer-7 agent: it emits
    sign IDs and parameter names, and the tutor loop sequences them like any other lesson.
    """

    name = "remediation"
    language_aware = True

    def __init__(
        self,
        dictionary: SignDictionary,
        *,
        max_depth: int = 3,
        max_steps: int = 9,
        branching: int = 2,
        mastery_threshold: float = MASTERY_THRESHOLD,
    ):
        self.dictionary = dictionary
        self.max_depth = max_depth
        self.max_steps = max_steps
        self.branching = branching
        self.mastery_threshold = mastery_threshold
        self._by_id = {s.sign_id: s for s in dictionary.signs}
        # (parameter, value) -> signs sharing it, easiest first. Built once; the descent
        # then costs a dict lookup per level instead of a scan of the dictionary.
        self._by_component: dict[tuple[str, str], list[Sign]] = {}
        for sign in sorted(dictionary.signs, key=lambda s: (s.curriculum.difficulty, s.sign_id)):
            for param in PARAMETERS:
                key = (param, getattr(sign.parameters, param))
                self._by_component.setdefault(key, []).append(sign)

    # -- helpers --

    def _mastery(self, sign_id: str, ctx: AgentContext) -> float:
        return float(ctx.mastery.get(sign_id, 0.0))

    def _mastered(self, sign_id: str, ctx: AgentContext) -> bool:
        return self._mastery(sign_id, ctx) >= self.mastery_threshold

    def _label(self, sign_id: str, ctx: AgentContext) -> str:
        sign = self._by_id.get(sign_id)
        if sign is None:
            return sign_id
        return sign.labels.ne if ctx.language == "ne" else sign.labels.en

    def _param_label(self, parameter: str, ctx: AgentContext) -> str:
        return _PARAM_LABEL.get(parameter, {}).get(ctx.language, parameter)

    def _anchor(
        self, sign: Sign, parameter: str, ctx: AgentContext, visited: set[str]
    ) -> Sign | None:
        """The best sign to rebuild ``parameter`` from: a mastered neighbour if one exists,
        otherwise the easiest unvisited neighbour that is no harder than ``sign``."""
        value = getattr(sign.parameters, parameter)
        pool = [
            s
            for s in self._by_component.get((parameter, value), [])
            if s.sign_id != sign.sign_id and s.sign_id not in visited
        ]
        mastered = [s for s in pool if self._mastered(s.sign_id, ctx)]
        if mastered:
            # Highest mastery wins — the surest footing, not merely the easiest sign.
            return max(mastered, key=lambda s: (self._mastery(s.sign_id, ctx), -s.curriculum.difficulty))
        easier = [s for s in pool if s.curriculum.difficulty <= sign.curriculum.difficulty]
        return easier[0] if easier else None

    def _component_reference(self, sign: Sign, parameter: str) -> str | None:
        """An easier sign the avatar can demo the isolated component with."""
        value = getattr(sign.parameters, parameter)
        for s in self._by_component.get((parameter, value), []):
            if s.sign_id != sign.sign_id:
                return s.sign_id
        return None

    # -- recursion --

    def _descend(
        self,
        sign: Sign,
        parameter: str,
        depth: int,
        ctx: AgentContext,
        visited: set[str],
        steps: list[DrillStep],
        state: dict,
    ) -> None:
        """Post-order walk: everything this sign rests on is emitted before the sign
        itself, so the finished plan reads foundation-first."""
        if sign.sign_id in visited:
            return
        visited.add(sign.sign_id)

        # Leave room for this level's own component + sign steps before recursing further.
        has_budget = depth < self.max_depth and len(steps) + 2 < self.max_steps
        descended = False   # did a deeper level take over the component drill?
        if not has_budget:
            state["truncated"] = True
        else:
            # Explicit prerequisites first — authored ordering beats inferred similarity.
            for prereq_id in sign.curriculum.prerequisites[: self.branching]:
                prereq = self._by_id.get(prereq_id)
                if prereq is None or prereq_id in visited or self._mastered(prereq_id, ctx):
                    continue
                self._descend(prereq, parameter, depth + 1, ctx, visited, steps, state)
                descended = True

            anchor = self._anchor(sign, parameter, ctx, visited)
            if anchor is not None:
                if self._mastered(anchor.sign_id, ctx):
                    # Floor of the recursion: something they can already do. Stop here.
                    visited.add(anchor.sign_id)
                    steps.append(
                        DrillStep(
                            kind="foundation",
                            depth=depth + 1,
                            sign_id=anchor.sign_id,
                            parameter=parameter,
                            component_value=getattr(anchor.parameters, parameter),
                            instruction=_FOUNDATION_TEXT[ctx.language].format(
                                label=self._label(anchor.sign_id, ctx),
                                parameter=self._param_label(parameter, ctx),
                            ),
                            reason=f"mastered sign sharing {parameter}",
                        )
                    )
                else:
                    self._descend(anchor, parameter, depth + 1, ctx, visited, steps, state)
                    descended = True

        # Isolate the component **once**, at the bottom of the ladder. Every level shares
        # the same parameter value by construction, so drilling it at each one would just
        # repeat the same instruction on the way back up.
        if not descended:
            value = getattr(sign.parameters, parameter)
            steps.append(
                DrillStep(
                    kind="component",
                    depth=depth,
                    sign_id=sign.sign_id,
                    parameter=parameter,
                    component_value=value,
                    reference_sign_id=self._component_reference(sign, parameter),
                    instruction=_COMPONENT_TEXT[parameter][ctx.language].format(value=value),
                    reason=f"isolate {parameter}={value}",
                )
            )

        # … then the sign itself, re-assembled.
        is_target = depth == 0
        template = _TARGET_TEXT if is_target else _SIGN_TEXT
        if not is_target and sign.sign_id in state.get("prerequisite_ids", set()):
            template = _PREREQ_TEXT
        steps.append(
            DrillStep(
                kind="target" if is_target else "sign",
                depth=depth,
                sign_id=sign.sign_id,
                parameter=parameter,
                instruction=template[ctx.language].format(
                    label=self._label(sign.sign_id, ctx),
                    parameter=self._param_label(parameter, ctx),
                ),
                reason="re-attempt the failed sign" if is_target else "supporting sign",
            )
        )

    # -- public API --

    def run(self, payload: RemediationRequest, ctx: AgentContext) -> RemediationPlan:
        sign = self._by_id.get(payload.sign_id)
        if sign is None:
            raise KeyError(payload.sign_id)
        parameter = payload.failed_parameter
        if parameter not in PARAMETERS:
            raise ValueError(f"failed_parameter must be one of {PARAMETERS}, got {parameter!r}")

        steps: list[DrillStep] = []
        state: dict = {
            "truncated": False,
            "prerequisite_ids": set(sign.curriculum.prerequisites),
        }
        self._descend(sign, parameter, 0, ctx, set(), steps, state)
        return RemediationPlan(
            target_sign_id=sign.sign_id,
            failed_parameter=parameter,
            steps=steps,
            depth_reached=max((s.depth for s in steps), default=0),
            truncated=bool(state["truncated"]),
        )

    def from_score(self, sign_id: str, score_result, ctx: AgentContext) -> RemediationPlan:
        """Convenience: build a plan straight from a :class:`ScoreResult`."""
        return self.run(
            RemediationRequest(
                sign_id=sign_id,
                failed_parameter=score_result.feedback_target,
                score=score_result.overall,
            ),
            ctx,
        )
