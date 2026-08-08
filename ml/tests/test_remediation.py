"""Recursive curriculum descent: does the ladder bottom out, and in the right order?"""

from __future__ import annotations

import pytest

from signbridge.agents.base import AgentContext
from signbridge.agents.curriculum import CurriculumAgent, LessonRequest
from signbridge.agents.remediation import RemediationAgent, RemediationRequest
from signbridge.vocabulary import build_dictionary

DICT = build_dictionary()
AGENT = RemediationAgent(DICT)


def _plan(sign_id="NSL_0001", parameter="handshape", mastery=None, language="en"):
    ctx = AgentContext(language=language, mastery=mastery or {})
    return AGENT.run(RemediationRequest(sign_id, parameter), ctx)


def test_plan_starts_at_the_bottom_and_ends_on_the_target():
    plan = _plan()
    assert plan.steps, "a failed sign must produce at least one drill"
    last = plan.steps[-1]
    assert last.kind == "target" and last.sign_id == "NSL_0001" and last.depth == 0
    # The ladder is walked bottom-up: the first step is the deepest one found.
    assert plan.steps[0].depth == plan.depth_reached


def test_component_is_isolated_exactly_once_at_the_bottom():
    """Every level of a descent shares the same parameter value, so drilling it at each
    one would repeat the same instruction on the way back up."""
    plan = _plan(parameter="movement")
    components = [s for s in plan.steps if s.kind == "component"]
    assert len(components) == 1
    assert components[0].parameter == "movement"
    assert components[0].depth == plan.depth_reached
    assert plan.failed_parameter == "movement"
    # The value drilled is the one the target sign actually uses.
    deepest_sign = DICT.by_id(components[0].sign_id)
    assert components[0].component_value == deepest_sign.parameters.movement
    assert deepest_sign.parameters.movement == DICT.by_id("NSL_0001").parameters.movement


def test_recursion_stops_at_mastered_material():
    """A mastered neighbour is the floor — the descent uses it and goes no deeper."""
    target = DICT.by_id("NSL_0003")
    neighbours = [
        s.sign_id
        for s in DICT.signs
        if s.sign_id != target.sign_id
        and s.parameters.handshape == target.parameters.handshape
    ]
    assert neighbours, "fixture assumption: NSL_0003 shares a handshape with something"

    unmastered = _plan("NSL_0003", "handshape")
    mastered = _plan("NSL_0003", "handshape", mastery={sid: 1.0 for sid in neighbours})

    foundations = [s for s in mastered.steps if s.kind == "foundation"]
    assert foundations, "a mastered neighbour should become the foundation step"
    assert foundations[0].sign_id in neighbours
    # It is the floor: nothing is drilled below it.
    assert foundations[0].depth == mastered.depth_reached
    assert not [s for s in mastered.steps if s.kind == "sign"]
    # Bottoming out early means a shorter ladder than descending through unknown signs.
    assert len(mastered.steps) <= len(unmastered.steps)


def test_depth_and_length_are_capped():
    agent = RemediationAgent(DICT, max_depth=2, max_steps=6)
    plan = agent.run(RemediationRequest("NSL_0005", "location"), AgentContext())
    assert plan.depth_reached <= 2
    assert len(plan.steps) <= 6


def test_no_sign_is_drilled_twice():
    """The visited set makes cycles in the component graph structurally impossible."""
    for parameter in ("handshape", "location", "movement", "orientation"):
        plan = _plan("NSL_0010", parameter)
        sign_steps = [s.sign_id for s in plan.steps if s.kind in ("sign", "target", "foundation")]
        assert len(sign_steps) == len(set(sign_steps))


def test_instructions_are_localized():
    en = _plan(language="en")
    ne = _plan(language="ne")
    assert all(s.instruction for s in en.steps + ne.steps)
    # Devanagari present in the Nepali plan, absent from the English one.
    assert any(any("ऀ" <= ch <= "ॿ" for ch in s.instruction) for s in ne.steps)
    assert not any(any("ऀ" <= ch <= "ॿ" for ch in s.instruction) for s in en.steps)


def test_unknown_sign_and_parameter_are_rejected():
    with pytest.raises(KeyError):
        _plan("NSL_9999")
    with pytest.raises(ValueError):
        _plan(parameter="vibe")


def test_lesson_carries_remediation_and_yields_new_material():
    agent = CurriculumAgent(DICT)
    ctx = AgentContext(language="en")
    plain = agent.run(LessonRequest(lesson_size=5), ctx)
    struggling = agent.run(
        LessonRequest(lesson_size=5, struggling=[("NSL_0001", "handshape")]), ctx
    )
    assert not plain.remediation
    assert struggling.remediation
    # Drilling a failure means less room for new signs, not more.
    assert len(struggling.new) < len(plain.new)


def test_struggling_sign_is_not_also_queued_as_a_plain_review():
    agent = CurriculumAgent(DICT)
    lesson = agent.run(
        LessonRequest(
            lesson_size=5,
            due_sign_ids=["NSL_0001", "NSL_0002"],
            struggling=[("NSL_0001", "location")],
        ),
        AgentContext(),
    )
    assert "NSL_0001" not in lesson.review
    assert "NSL_0001" not in lesson.new, "a sign being drilled is not also new material"
    assert "NSL_0002" in lesson.review


def test_unknown_struggling_entry_does_not_break_the_lesson():
    agent = CurriculumAgent(DICT)
    lesson = agent.run(
        LessonRequest(lesson_size=5, struggling=[("NSL_9999", "handshape"), ("NSL_0001", "nope")]),
        AgentContext(),
    )
    assert lesson.remediation == []
    assert lesson.new
