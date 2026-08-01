"""Practice Partner agent — drives a constrained-domain practice dialogue.

Language-aware. Given a scenario and the learner's last turn, it picks the next sign for
the learner to produce and a short localized prompt. Template-driven and scenario-scoped so
it never asks for a sign outside the current lesson (keeping practice bounded and reliable).

STUB depth: scenarios are hand-authored here. A richer version can route the prompt text
through an LLM per language pair, but the *next sign* selection should stay rule-bound.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import AgentContext

# Minimal scenarios: an ordered list of sign_ids the learner practices in turn.
SCENARIOS: dict[str, list[str]] = {
    "greetings": ["NSL_0001", "NSL_0009", "NSL_0002", "NSL_0010"],
    "family": ["NSL_0015", "NSL_0016", "NSL_0017", "NSL_0018"],
    "numbers": ["NSL_0021", "NSL_0022", "NSL_0023", "NSL_0024", "NSL_0025"],
}

_PROMPTS = {
    "en": {
        "start": "Let's practice. Sign: {label}",
        "next": "Good. Now sign: {label}",
        "done": "That completes this scenario. Well done!",
    },
    "ne": {
        "start": "अभ्यास गरौं। संकेत गर्नुहोस्: {label}",
        "next": "राम्रो। अब संकेत गर्नुहोस्: {label}",
        "done": "यो परिदृश्य पूरा भयो। शाबास!",
    },
}


@dataclass
class PartnerTurn:
    scenario: str
    prompt: str
    expected_sign_id: str | None
    finished: bool


class PracticePartnerAgent:
    name = "practice_partner"
    language_aware = True

    def __init__(self, dictionary=None):
        # Optional dictionary provides labels; ctx.metadata["labels"] can override.
        self._labels: dict[str, dict[str, str]] = {}
        if dictionary is not None:
            self._labels = {
                s.sign_id: {"en": s.labels.en, "ne": s.labels.ne} for s in dictionary.signs
            }

    def label_for(self, sign_id: str, ctx: AgentContext) -> str:
        meta = ctx.metadata.get("labels", {})
        entry = meta.get(sign_id) if isinstance(meta, dict) else None
        entry = entry or self._labels.get(sign_id, {})
        return entry.get(ctx.language, sign_id)

    def run(self, payload: dict, ctx: AgentContext) -> PartnerTurn:
        """payload: {"scenario": str, "completed": [sign_id, ...]}"""
        scenario = payload.get("scenario", "greetings")
        completed = list(payload.get("completed", []))
        seq = SCENARIOS.get(scenario, [])
        remaining = [s for s in seq if s not in completed]
        lang = ctx.language

        if not remaining:
            return PartnerTurn(scenario, _PROMPTS[lang]["done"], None, finished=True)

        nxt = remaining[0]
        key = "start" if not completed else "next"
        prompt = _PROMPTS[lang][key].format(label=self.label_for(nxt, ctx))
        return PartnerTurn(scenario, prompt, expected_sign_id=nxt, finished=False)
