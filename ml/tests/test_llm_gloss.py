"""LLM gloss agent: the LLM path is optional and must degrade to the heuristic. These tests
inject a fake chat model, so they run without an API key or the `llm` extra installed."""

from __future__ import annotations

from signbridge.agents.base import AgentContext
from signbridge.agents.gloss import GlossTranslationAgent
from signbridge.agents.llm_gloss import (
    LLMGlossTranslationAgent,
    llm_enabled,
    make_gloss_agent,
)
from signbridge.schema import load_dictionary


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    """Stands in for ChatGroq: returns a canned reply regardless of the prompt."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list = []

    def invoke(self, messages):
        self.calls.append(messages)
        return _FakeResp(self.content)


def _dict():
    return load_dictionary()


def test_make_gloss_agent_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("SIGNBRIDGE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert not llm_enabled()
    agent = make_gloss_agent(_dict())
    assert isinstance(agent, GlossTranslationAgent)


def test_agent_without_llm_matches_heuristic():
    d = _dict()
    agent = LLMGlossTranslationAgent(d)
    agent._llm = None  # simulate no key / dep
    ctx = AgentContext(language="en")
    assert agent.run("hello", ctx).gloss_string() == GlossTranslationAgent(d).run("hello", ctx).gloss_string()


def test_llm_reply_maps_codes_and_fingerspells_unknown():
    d = _dict()
    code = d.signs[0].gloss_code  # a real gloss code from the dictionary
    agent = LLMGlossTranslationAgent(d)
    agent._llm = _FakeLLM('{"gloss": ["%s", "fs(xyz)", "TOTALLY_FAKE"], "eyebrows": "raised"}' % code)

    res = agent.run("whatever", AgentContext(language="en"))
    glosses = [t.gloss for t in res.tokens]
    assert code in glosses  # valid code mapped to its sign
    assert res.tokens[glosses.index(code)].sign_id == d.signs[0].sign_id
    assert "fs(xyz)" in glosses  # explicit fingerspell kept
    assert "fs(totally_fake)" in glosses  # invented code demoted to fingerspelling, not a sign
    assert res.sentence_nmm.get("eyebrows") == "raised"


def test_malformed_llm_reply_falls_back_to_heuristic():
    d = _dict()
    agent = LLMGlossTranslationAgent(d)
    agent._llm = _FakeLLM("not json at all")
    ctx = AgentContext(language="en")
    # Unparseable -> heuristic result (non-empty for a known word).
    assert agent.run("hello", ctx).gloss_string() == GlossTranslationAgent(d).run("hello", ctx).gloss_string()
