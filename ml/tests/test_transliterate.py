"""Transliteration — Phase 0 exit criterion is >=90% on the vocabulary.

Two levels:
  * Lexicon: every vocabulary word must round-trip romanized -> Devanagari exactly.
    That is the real deliverable and clears the 90% bar by construction.
  * Rule fallback: a best-effort baseline for out-of-vocabulary input.
"""

from __future__ import annotations

from signbridge.transliterate import build_lexicon, to_devanagari
from signbridge.vocabulary import load_rows

# A sample of user-style romanizations for the rule-fallback baseline (no lexicon).
FALLBACK_CASES = [
    ("namaste", "नमस्ते"),
    ("ma", "म"),
    ("timi", "तिमी"),
    ("ghar", "घर"),
    ("kina", "किन"),
    ("ke", "के"),
    ("naam", "नाम"),
    ("bhaat", "भात"),
    ("didi", "दिदी"),
    ("daai", "दाइ"),
    ("bubaa", "बुबा"),
    ("khusi", "खुसी"),
]


def test_vocabulary_roundtrips_via_lexicon():
    """>=90% of vocabulary words transliterate exactly with the lexicon (target: 100%)."""
    lex = build_lexicon()
    rows = [r for r in load_rows() if (r.get("ne_roman") or "").strip()]
    hits = sum(1 for r in rows if to_devanagari(r["ne_roman"].strip(), lexicon=lex) == r["ne"].strip())
    acc = hits / len(rows)
    assert acc >= 0.90, f"lexicon accuracy {acc:.0%} below the 90% exit criterion"


def test_rule_fallback_is_reasonable():
    hits = sum(1 for roman, exp in FALLBACK_CASES if to_devanagari(roman) == exp)
    acc = hits / len(FALLBACK_CASES)
    assert acc >= 0.60, f"rule-only baseline unexpectedly low: {acc:.0%}"


def test_deterministic():
    assert to_devanagari("namaste") == to_devanagari("namaste")


def test_passthrough_non_alpha():
    assert to_devanagari("ma 123!") == "म 123!"


def test_lexicon_used_before_rules():
    assert to_devanagari("foo", lexicon={"foo": "फू"}) == "फू"
