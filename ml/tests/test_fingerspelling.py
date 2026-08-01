"""Fingerspelling alphabet + interim classifier."""

from __future__ import annotations

import numpy as np

from signbridge.fingerspelling import CHARS, HAND_FEATURE_DIM, ROMANS, spellable
from signbridge.models.linear_model import LinearSignClassifier


def test_alphabet_consistent():
    assert len(CHARS) == len(ROMANS) >= 40
    assert len(set(CHARS)) == len(CHARS)  # unique characters


def test_spellable_splits_known_chars():
    # नमस्ते -> न म ... (skips the halant/combining vowel signs we don't fingerspell)
    chars = spellable("नमस्ते")
    assert "न" in chars and "म" in chars
    assert all(c in set(CHARS) for c in chars)


def test_classifier_generalizes_to_input_dim():
    # A tiny separable problem at the hand-feature dimension.
    rng = np.random.default_rng(0)
    protos = rng.normal(0, 1, (5, HAND_FEATURE_DIM)).astype(np.float32)
    X = np.repeat(protos, 20, axis=0) + rng.normal(0, 0.05, (100, HAND_FEATURE_DIM)).astype(np.float32)
    y = np.repeat(np.arange(5), 20)
    clf = LinearSignClassifier([f"c{i}" for i in range(5)], input_dim=HAND_FEATURE_DIM).fit(X, y, epochs=200)
    assert clf.score(X, y) > 0.95
