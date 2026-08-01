"""Sign dictionary, vocabulary, and transliteration endpoints."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from signbridge.schema import SignDictionary
from signbridge.transliterate import build_lexicon, to_devanagari
from signbridge.vocabulary import build_dictionary

from ..schemas import SignOut, TransliterateIn, TransliterateOut

router = APIRouter(prefix="/signs", tags=["signs"])


@lru_cache(maxsize=1)
def _dictionary() -> SignDictionary:
    # Build from the CSV on first use; cheap and avoids requiring the generated JSON.
    return build_dictionary()


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, str]:
    return build_lexicon()


def _to_out(sign) -> SignOut:
    return SignOut(
        sign_id=sign.sign_id,
        en=sign.labels.en,
        ne=sign.labels.ne,
        ne_roman=sign.labels.ne_roman,
        gloss_code=sign.gloss_code,
        category=sign.curriculum.category,
        difficulty=sign.curriculum.difficulty,
        clip_ref=sign.clip_ref,
    )


@router.get("", response_model=list[SignOut])
def list_signs(category: str | None = None) -> list[SignOut]:
    signs = _dictionary().signs
    if category:
        signs = [s for s in signs if s.curriculum.category == category]
    return [_to_out(s) for s in signs]


@router.get("/{sign_id}", response_model=SignOut)
def get_sign(sign_id: str) -> SignOut:
    try:
        return _to_out(_dictionary().by_id(sign_id))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown sign_id: {sign_id}")


@router.post("/transliterate", response_model=TransliterateOut, tags=["nepali"])
def transliterate(payload: TransliterateIn) -> TransliterateOut:
    """Romanized Nepali -> Devanagari (lexicon-first, rule fallback)."""
    return TransliterateOut(
        input=payload.text,
        devanagari=to_devanagari(payload.text, lexicon=_lexicon()),
    )
