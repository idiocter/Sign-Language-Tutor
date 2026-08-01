"""Agent layer (TECH_STACK.md Layer 7).

Agents operate on **symbolic data** — sign IDs, DTW scores, mastery state — never raw
video. Keeping the vision model outside the agent loop is a hard rule; otherwise latency
destroys the experience.

Orchestration is a plain typed dispatcher, not a framework. From the plan: "Do not add a
framework before you feel the pain." Six agents with mostly linear flow don't need
LangGraph yet.

Language-aware agents (Critique, Gloss Translation, Practice Partner) need **separate
prompts per language pair** — Nepali is SOV, English is SVO, NSL is topic-comment.
"""

from .animation import AnimationDirectorAgent  # noqa: F401
from .base import Agent, AgentContext  # noqa: F401
from .critique import CritiqueAgent  # noqa: F401
from .curriculum import CurriculumAgent  # noqa: F401
from .data_curator import DataCuratorAgent  # noqa: F401
from .gloss import GlossTranslationAgent  # noqa: F401
from .practice_partner import PracticePartnerAgent  # noqa: F401

# The six agents from TECH_STACK.md Layer 7. Vision stays outside this loop — agents only
# ever see symbolic data (sign IDs, scores, mastery), never raw video.
ALL_AGENTS = [
    "curriculum",
    "critique",
    "gloss_translation",
    "animation_director",
    "practice_partner",
    "data_curator",
]
