"""Roman → Devanagari transliteration (Phase 0 deliverable).

Nepali users overwhelmingly type Romanized Nepali ("namaste", "dhanyabaad"). Search,
labels, and fingerspelling all need to map that back to Devanagari (नमस्ते, धन्यवाद).

Design: **lexicon first, rules second** — exactly how production transliterators work.

  1. A lexicon of known words (built from the vocabulary's ``ne_roman`` → ``ne`` columns)
     is consulted first. Romanization is inherently ambiguous (does final ``-i`` mean इ or
     ई? does ``khaana`` end in न or ना?), so no rule set alone is reliable on real Nepali.
     For the words the app actually cares about, we already know the correct Devanagari.
  2. Unknown words fall back to a self-contained rule engine (a phonetic approximation),
     or to ``indic_transliteration`` (ITRANS) when that optional package is installed.

Exit criteria from PROJECT_PLAN.md: ≥90% on the test set. The lexicon-backed
transliterator clears it on the vocabulary; the rule fallback is a best-effort baseline
for out-of-vocabulary input.
"""

from __future__ import annotations

import re
from functools import lru_cache

# --- Rule-based fallback ----------------------------------------------------
# Ordered longest-first so multi-character clusters ("chh", "aa") win over their
# prefixes ("ch", "a"). This is a phonetic approximation of the common Nepali
# romanization conventions, not a formal ITRANS/IAST implementation.

_VOWELS_INDEPENDENT = {
    "au": "औ", "ai": "ऐ", "aa": "आ", "ee": "ई", "ii": "ई", "oo": "ऊ", "uu": "ऊ",
    "a": "अ", "i": "इ", "u": "उ", "e": "ए", "o": "ओ",
}
# Vowel signs (matras) that attach to a preceding consonant.
_VOWEL_SIGNS = {
    "au": "ौ", "ai": "ै", "aa": "ा", "ee": "ी", "ii": "ी", "oo": "ू", "uu": "ू",
    "a": "", "i": "ि", "u": "ु", "e": "े", "o": "ो",
}
_CONSONANTS = {
    "kh": "ख", "gh": "घ", "ng": "ङ",
    "chh": "छ", "ch": "च", "jh": "झ",
    "th": "थ", "dh": "ध", "ph": "फ", "bh": "भ",
    "sh": "श", "shh": "ष",
    "k": "क", "g": "ग", "c": "च", "j": "ज", "t": "त", "d": "द", "n": "न",
    "p": "प", "b": "ब", "m": "म", "y": "य", "r": "र", "l": "ल", "w": "व",
    "v": "व", "s": "स", "h": "ह",
}
_HALANT = "्"

# Longest-first key lists so the greedy matcher prefers clusters.
_CONS_KEYS = sorted(_CONSONANTS, key=len, reverse=True)
_VOWEL_KEYS = sorted(_VOWELS_INDEPENDENT, key=len, reverse=True)


def _match(text: str, pos: int, keys: list[str]) -> str | None:
    for k in keys:
        if text.startswith(k, pos):
            return k
    return None


# Word-final short vowels are usually long in Nepali romanization ("timi" -> तिमी).
_FINAL_LONG = {"i": "ी", "u": "ू"}


def _fallback_word(word: str) -> str:
    """Transliterate a single lowercase ASCII word."""
    out: list[str] = []
    i = 0
    n = len(word)
    while i < n:
        cons = _match(word, i, _CONS_KEYS)
        if cons is not None:
            i += len(cons)
            vow = _match(word, i, _VOWEL_KEYS)
            if vow is not None:
                sign = _VOWEL_SIGNS[vow]
                if i + len(vow) >= n and vow in _FINAL_LONG:
                    sign = _FINAL_LONG[vow]  # final -i/-u tend to be long
                out.append(_CONSONANTS[cons] + sign)
                i += len(vow)
            else:
                # No following vowel: bare consonant carries the inherent 'a' when
                # word-final, otherwise a halant to cluster with the next consonant.
                if i >= n:
                    out.append(_CONSONANTS[cons])
                else:
                    out.append(_CONSONANTS[cons] + _HALANT)
            continue

        vow = _match(word, i, _VOWEL_KEYS)
        if vow is not None:
            out.append(_VOWELS_INDEPENDENT[vow])
            i += len(vow)
            continue

        # Unknown character (digit, punctuation) — pass through unchanged.
        out.append(word[i])
        i += 1
    return "".join(out)


def _fallback(text: str) -> str:
    return re.sub(r"[A-Za-z]+", lambda m: _fallback_word(m.group(0).lower()), text)


# --- Optional high-quality backend ------------------------------------------

@lru_cache(maxsize=1)
def _indic_backend():
    """Return the indic_transliteration transliterate fn, or None if unavailable."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate as _t

        def run(text: str) -> str:
            return _t(text, sanscript.ITRANS, sanscript.DEVANAGARI)

        return run
    except Exception:  # pragma: no cover - depends on optional install
        return None


def to_devanagari(
    text: str,
    *,
    backend: str = "fallback",
    lexicon: dict[str, str] | None = None,
) -> str:
    """Transliterate Romanized Nepali to Devanagari.

    Parameters
    ----------
    text:
        Romanized input, e.g. ``"namaste"``. Split into words; each word is looked up in
        ``lexicon`` first, then transliterated by the chosen backend.
    backend:
        ``"fallback"`` (default) uses the deterministic built-in rules. ``"indic"`` forces
        ``indic_transliteration`` (ITRANS) and raises if it is missing.
    lexicon:
        Optional ``{romanized_lower: devanagari}`` map consulted before any rules. Build
        one from the vocabulary with :func:`build_lexicon`.
    """
    if backend == "indic":
        engine = _indic_backend()
        if engine is None:
            raise RuntimeError("indic_transliteration is not installed")
    elif backend == "fallback":
        engine = _fallback_word
    else:
        raise ValueError(f"unknown backend: {backend!r}")

    lex = lexicon or {}

    def render_word(m) -> str:
        w = m.group(0)
        hit = lex.get(w.lower())
        return hit if hit is not None else engine(w.lower())

    return re.sub(r"[A-Za-z]+", render_word, text)


def build_lexicon(vocab_path=None) -> dict[str, str]:
    """Build a ``{romanized: devanagari}`` lexicon from the vocabulary CSV.

    This is the high-confidence path: for every sign we already store the canonical
    Romanization and Devanagari, so known words transliterate exactly.
    """
    import csv

    from .config import VOCAB_PATH

    path = vocab_path or VOCAB_PATH
    lex: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            roman = (row.get("ne_roman") or "").strip().lower()
            deva = (row.get("ne") or "").strip()
            if roman and deva:
                lex[roman] = deva
    return lex
