"""Text -> NSL sign production (Phase 2).

Pipeline: text -> Gloss Translation agent -> gloss sequence -> Animation Director agent ->
timed animation plan (procedural pose + ARKit facial track per sign). The frontend avatar
plays the plan with co-articulation blending.

Also exposes the clip manifest: which signs have an authored glTF clip vs. fall back to the
procedural pose.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from signbridge.agents.animation import AnimationDirectorAgent
from signbridge.agents.base import AgentContext
from signbridge.agents.llm_gloss import make_gloss_agent

from .signs import _dictionary

router = APIRouter(tags=["produce"])

# Authored clips live here (gitignored binaries). Empty until a clip is authored in Blender.
CLIP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web" / "public" / "clips"


class ProduceIn(BaseModel):
    text: str = Field(..., examples=["hello thank you"])
    language: str = "en"


class StepOut(BaseModel):
    sign_id: str
    gloss: str
    clip_ref: str | None
    start_ms: int
    duration_ms: int
    crossfade_ms: int
    pose: dict | None
    facial: dict


class ProduceOut(BaseModel):
    gloss: str
    sentence_nmm: dict
    total_ms: int
    has_facial_motion: bool
    steps: list[StepOut]


def _clip_available(clip_ref: str | None) -> bool:
    if not clip_ref:
        return False
    return (CLIP_DIR.parent / clip_ref).exists() or (CLIP_DIR / Path(clip_ref).name).exists()


@router.post("/produce", response_model=ProduceOut)
def produce(payload: ProduceIn) -> ProduceOut:
    d = _dictionary()
    gloss_agent = make_gloss_agent(d)  # LLM-backed when a key is set, else the heuristic
    anim_agent = AnimationDirectorAgent(d)
    ctx = AgentContext(language=payload.language)

    gloss = gloss_agent.run(payload.text, ctx)
    sign_ids = [t.sign_id for t in gloss.tokens if t.sign_id]
    plan = anim_agent.run(sign_ids, ctx)

    steps = []
    for s in plan.steps:
        clip_ref = s.clip_ref if _clip_available(s.clip_ref) else None
        steps.append(
            StepOut(
                sign_id=s.sign_id,
                gloss=s.gloss,
                clip_ref=clip_ref,  # only set when an authored .glb is actually present
                start_ms=s.start_ms,
                duration_ms=s.duration_ms,
                crossfade_ms=s.crossfade_ms,
                pose=s.pose,
                facial=s.facial,
            )
        )
    return ProduceOut(
        gloss=gloss.gloss_string(),
        sentence_nmm=gloss.sentence_nmm,
        total_ms=plan.total_ms,
        has_facial_motion=plan.has_facial_motion(),
        steps=steps,
    )


@router.get("/produce/sign", response_model=ProduceOut)
def produce_sign(sign_id: str) -> ProduceOut:
    """Animation plan for a single sign — used by the tutor to show the avatar signing it."""
    d = _dictionary()
    try:
        d.by_id(sign_id)
    except KeyError:
        raise HTTPException(404, f"unknown sign_id: {sign_id}")
    plan = AnimationDirectorAgent(d).run([sign_id], AgentContext())
    steps = [
        StepOut(
            sign_id=s.sign_id,
            gloss=s.gloss,
            clip_ref=s.clip_ref if _clip_available(s.clip_ref) else None,
            start_ms=s.start_ms,
            duration_ms=s.duration_ms,
            crossfade_ms=s.crossfade_ms,
            pose=s.pose,
            facial=s.facial,
        )
        for s in plan.steps
    ]
    return ProduceOut(
        gloss=steps[0].gloss if steps else "",
        sentence_nmm={},
        total_ms=plan.total_ms,
        has_facial_motion=plan.has_facial_motion(),
        steps=steps,
    )


@router.get("/clips/manifest", tags=["produce"])
def clip_manifest() -> dict:
    """Per-sign clip status: 'authored' if a .glb exists, else 'procedural'."""
    d = _dictionary()
    signs = []
    authored = 0
    for s in d.signs:
        has = _clip_available(s.clip_ref)
        authored += int(has)
        signs.append({"sign_id": s.sign_id, "clip_ref": s.clip_ref, "status": "authored" if has else "procedural"})
    return {"total": len(signs), "authored": authored, "procedural": len(signs) - authored, "signs": signs}
