"""Gloss Translation agent — spoken/written text -> NSL gloss + non-manual markers.

Language-aware and the reason the plan insists on it: Nepali is SOV, English is SVO, NSL
is topic-comment. A shared prompt produces bad gloss for at least one language, so the
reordering rule is chosen per source language.

This is a **transparent heuristic**, not a trained translator: tokenize, map known words to
their sign ``gloss_code`` via the dictionary, drop function words, reorder toward
topic-comment, and attach NMM (raised brows for yes/no, furrowed for wh-questions). It must
be validated with a linguist and deaf advisors before it is trusted — treat its output as a
draft. When you build the real model, keep this as the fallback and the eval baseline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schema import SignDictionary
from .base import AgentContext

# Function words to drop when glossing (sign languages omit most of these).
_STOPWORDS = {
    "en": {"a", "an", "the", "is", "are", "am", "to", "of", "do", "does", "did", "please", "will"},
    "ne": {"ho", "ho।", "cha", "chha", "ra", "ma", "lai", "ko", "le", "garne", "garnu"},
}
_WH = {"en": {"what", "where", "who", "when", "why", "how"}, "ne": {"ke", "kahaa", "ko", "kahile", "kina", "kasari"}}


@dataclass
class GlossToken:
    gloss: str
    sign_id: str | None = None
    nmm: dict[str, str] = field(default_factory=dict)


@dataclass
class GlossResult:
    tokens: list[GlossToken]
    sentence_nmm: dict[str, str]  # sentence-level markers (question type, etc.)

    def gloss_string(self) -> str:
        return " ".join(t.gloss for t in self.tokens)


class GlossTranslationAgent:
    name = "gloss_translation"
    language_aware = True

    def __init__(self, dictionary: SignDictionary):
        self.dictionary = dictionary
        self._lookup = self._build_lookup(dictionary)

    @staticmethod
    def _build_lookup(d: SignDictionary) -> dict[str, tuple[str, str]]:
        """word (lowercased) -> (gloss_code, sign_id) from en, ne, and ne_roman labels."""
        table: dict[str, tuple[str, str]] = {}
        for s in d.signs:
            keys = [s.labels.en.lower(), s.labels.ne]
            if s.labels.ne_roman:
                keys.append(s.labels.ne_roman.lower())
            for k in keys:
                for tok in k.split():
                    table.setdefault(tok, (s.gloss_code, s.sign_id))
        return table

    def run(self, text: str, ctx: AgentContext) -> GlossResult:
        lang = ctx.language
        raw = re.findall(r"[\wऀ-ॿ]+", text.lower())
        is_question = "?" in text or any(w in _WH[lang] for w in raw)

        tokens: list[GlossToken] = []
        for w in raw:
            if w in _STOPWORDS[lang]:
                continue
            hit = self._lookup.get(w)
            if hit:
                tokens.append(GlossToken(gloss=hit[0], sign_id=hit[1]))
            else:
                # Unknown word -> mark for fingerspelling rather than dropping silently.
                tokens.append(GlossToken(gloss=f"fs({w})"))

        tokens = self._reorder(tokens, lang, is_question)
        sentence_nmm = {}
        if is_question:
            # wh-questions: furrowed brows; yes/no: raised brows (NSL non-manual grammar).
            sentence_nmm["eyebrows"] = "furrowed" if any(w in _WH[lang] for w in raw) else "raised"
        return GlossResult(tokens=tokens, sentence_nmm=sentence_nmm)

    @staticmethod
    def _reorder(tokens: list[GlossToken], lang: str, is_question: bool) -> list[GlossToken]:
        """Nudge toward NSL topic-comment. A minimal, documented heuristic.

        - English (SVO) and Nepali (SOV) both tend to end near the comment for the simple
          constrained-domain sentences we target, so token order is preserved.
        - Wh/question glosses move to the end (common in NSL), while fingerspelling and all
          other tokens are kept — nothing is silently dropped.

        Full topic-comment reordering needs a linguist + deaf-advisor review; this seam is
        where a trained model or richer rules plug in later.
        """
        wh_glosses = {g.upper() for g in _WH[lang]}
        questiony = [t for t in tokens if t.gloss.upper() in wh_glosses]
        rest = [t for t in tokens if t.gloss.upper() not in wh_glosses]
        return rest + questiony if is_question else tokens
