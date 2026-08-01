"""Interpreter mode (Phase 4) — constrained-domain, bidirectional.

Two directions:
  * **Text -> Sign** is handled by /produce (this module doesn't duplicate it).
  * **Sign -> Text** lives here: a recognized sign sequence -> gloss -> spoken-language text.

Honest scope (PROJECT_PLAN.md Phase 4 + TECH_STACK.md Layer 5): full continuous recognition
(CTC) and a fine-tuned Nepali Whisper/TTS are out of reach here. So:
  * Sign->Text assembles text from a sequence of already-recognized sign IDs (the isolated
    recognition model produces those). It's the gloss->text seam; swap in a real
    gloss-to-text model when available.
  * ASR (speech in) and TTS (speech out) run in the browser via the Web Speech API, with
    text input/output **always available as the fallback** the plan requires.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .signs import _dictionary

router = APIRouter(prefix="/interpret", tags=["interpret"])


class SignToTextIn(BaseModel):
    sign_ids: list[str] = Field(..., examples=[["NSL_0001", "NSL_0002"]])
    language: str = "en"


class SignToTextOut(BaseModel):
    gloss: str
    text: str
    text_en: str
    text_ne: str
    unknown: list[str]


@router.post("/sign-to-text", response_model=SignToTextOut)
def sign_to_text(payload: SignToTextIn) -> SignToTextOut:
    """Assemble recognized signs into spoken-language text (constrained domain).

    Interim assembly joins the signs' labels; a trained gloss->text model would handle
    NSL topic-comment -> SVO/SOV reordering. Both en and ne are returned so the client can
    show text even when a Nepali TTS voice is unavailable.
    """
    d = _dictionary()
    gloss: list[str] = []
    en_words: list[str] = []
    ne_words: list[str] = []
    unknown: list[str] = []
    for sid in payload.sign_ids:
        try:
            s = d.by_id(sid)
        except KeyError:
            unknown.append(sid)
            continue
        gloss.append(s.gloss_code)
        en_words.append(s.labels.en)
        ne_words.append(s.labels.ne)

    if not gloss and payload.sign_ids:
        raise HTTPException(422, "no known signs in sequence")

    text_en = " ".join(en_words).strip()
    text_ne = " ".join(ne_words).strip()
    return SignToTextOut(
        gloss=" ".join(gloss),
        text=text_ne if payload.language == "ne" else text_en,
        text_en=text_en,
        text_ne=text_ne,
        unknown=unknown,
    )
