"""Devanagari manual alphabet for fingerspelling (Phase 1.5).

A separate, simpler task than isolated-sign recognition: static single-frame handshape
classification for the Devanagari manual alphabet. TECH_STACK.md picks MobileNetV3 on a
cropped hand image; here we use the hand *landmarks* (21 points) so the interim model runs
with numpy + onnx, matching the rest of the runnable-now pipeline. The `full` extra's
`models/fingerspelling.py` MobileNetV3 remains the production path for image input.

The character set below is the manual alphabet's target labels. Exit criterion: ≥90% top-1
(PROJECT_PLAN.md Phase 1.5). Handshapes here are the real signal to collect with signers;
the interim model trains on synthetic hand landmarks and measures the pipeline, not real
fingerspelling.
"""

from __future__ import annotations

# (Devanagari character, romanization). Consonants + independent vowels + a few conjuncts.
DEVANAGARI_ALPHABET: list[tuple[str, str]] = [
    # vowels
    ("अ", "a"), ("आ", "aa"), ("इ", "i"), ("ई", "ii"), ("उ", "u"), ("ऊ", "uu"),
    ("ए", "e"), ("ऐ", "ai"), ("ओ", "o"), ("औ", "au"), ("अं", "am"), ("अः", "ah"),
    # consonants
    ("क", "ka"), ("ख", "kha"), ("ग", "ga"), ("घ", "gha"), ("ङ", "nga"),
    ("च", "cha"), ("छ", "chha"), ("ज", "ja"), ("झ", "jha"), ("ञ", "nya"),
    ("ट", "ta"), ("ठ", "tha"), ("ड", "da"), ("ढ", "dha"), ("ण", "nna"),
    ("त", "ta2"), ("थ", "tha2"), ("द", "da2"), ("ध", "dha2"), ("न", "na"),
    ("प", "pa"), ("फ", "pha"), ("ब", "ba"), ("भ", "bha"), ("म", "ma"),
    ("य", "ya"), ("र", "ra"), ("ल", "la"), ("व", "wa"),
    ("श", "sha"), ("ष", "ssa"), ("स", "sa"), ("ह", "ha"),
    ("क्ष", "ksha"), ("त्र", "tra"), ("ज्ञ", "gya"),
]

CHARS = [c for c, _ in DEVANAGARI_ALPHABET]
ROMANS = [r for _, r in DEVANAGARI_ALPHABET]

# Single-frame hand feature dimension: 21 landmarks x 3.
HAND_FEATURE_DIM = 21 * 3


def char_index(ch: str) -> int:
    return CHARS.index(ch)


def spellable(text: str) -> list[str]:
    """Split a Devanagari string into fingerspellable base characters we model.

    Best-effort: matches multi-codepoint conjuncts first, then single chars we know,
    skipping combining marks we don't fingerspell separately.
    """
    known = set(CHARS)
    out: list[str] = []
    i = 0
    # try 3-, 2-, 1-length windows (conjuncts like क्ष are multi-codepoint)
    while i < len(text):
        matched = None
        for span in (3, 2, 1):
            chunk = text[i : i + span]
            if chunk in known:
                matched = chunk
                i += span
                break
        if matched:
            out.append(matched)
        else:
            i += 1  # skip unknown/combining
    return out
