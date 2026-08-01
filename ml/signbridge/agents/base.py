"""Agent base contract and a minimal typed orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Language = Literal["en", "ne"]


@dataclass
class AgentContext:
    """Everything an agent may read. Symbolic only — no video, no landmarks."""

    language: Language = "en"
    mastery: dict[str, float] = field(default_factory=dict)  # sign_id -> 0..1
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    """All agents take a typed input + context and return a typed structured output."""

    name: str
    language_aware: bool

    def run(self, payload: object, ctx: AgentContext) -> object: ...
