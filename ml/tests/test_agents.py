"""Layer-7 agents: gloss, animation, practice partner, data curator."""

from __future__ import annotations

import numpy as np

from signbridge.agents import (
    AnimationDirectorAgent,
    DataCuratorAgent,
    GlossTranslationAgent,
    PracticePartnerAgent,
)
from signbridge.agents.base import AgentContext
from signbridge.config import FEATURE_DIM, SEQ_LEN
from signbridge.vocabulary import build_dictionary

DICT = build_dictionary()


def test_gloss_maps_known_words_and_flags_unknown():
    agent = GlossTranslationAgent(DICT)
    res = agent.run("hello friend", AgentContext(language="en"))
    glosses = res.gloss_string()
    assert "HELLO" in glosses
    # unknown words become fingerspelling tokens, never silently dropped
    res2 = agent.run("hello zzzq", AgentContext(language="en"))
    assert any(t.gloss.startswith("fs(") for t in res2.tokens)


def test_gloss_question_sets_nmm():
    agent = GlossTranslationAgent(DICT)
    res = agent.run("what", AgentContext(language="en"))
    assert res.sentence_nmm.get("eyebrows") == "furrowed"


def test_animation_plan_has_crossfade_and_facial():
    agent = AnimationDirectorAgent(DICT)
    plan = agent.run(["NSL_0001", "NSL_0002"], AgentContext())
    assert len(plan.steps) == 2
    assert plan.steps[0].crossfade_ms == 0
    assert plan.steps[1].crossfade_ms > 0
    assert plan.total_ms > 0


def test_practice_partner_walks_scenario():
    agent = PracticePartnerAgent(DICT)
    first = agent.run({"scenario": "greetings", "completed": []}, AgentContext(language="ne"))
    assert first.expected_sign_id == "NSL_0001" and not first.finished
    done = agent.run(
        {"scenario": "greetings", "completed": ["NSL_0001", "NSL_0009", "NSL_0002", "NSL_0010"]},
        AgentContext(language="en"),
    )
    assert done.finished


def test_data_curator_flags_bad_takes():
    agent = DataCuratorAgent()
    good = np.random.default_rng(0).normal(size=(SEQ_LEN, FEATURE_DIM)).astype(np.float32)
    static = np.zeros((SEQ_LEN, FEATURE_DIM), dtype=np.float32)
    short = np.random.default_rng(1).normal(size=(5, FEATURE_DIM)).astype(np.float32)
    reports = agent.run([("good", good), ("static", static), ("short", short)])
    by_key = {r.key: r for r in reports}
    assert by_key["good"].ok
    assert "near_static" in by_key["static"].flags
    assert "no_hands" in by_key["static"].flags
    assert "too_short" in by_key["short"].flags


def test_data_curator_detects_duplicates():
    agent = DataCuratorAgent()
    seq = np.random.default_rng(2).normal(size=(SEQ_LEN, FEATURE_DIM)).astype(np.float32)
    reports = agent.run([("a", seq), ("b", seq.copy())])
    assert reports[1].duplicate_of == "a"
