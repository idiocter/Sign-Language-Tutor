"""Vocabulary + schema validation."""

from __future__ import annotations

import pytest

from signbridge.schema import SignDictionary
from signbridge.vocabulary import build_dictionary


def test_vocabulary_compiles():
    d = build_dictionary()
    assert isinstance(d, SignDictionary)
    assert len(d.signs) >= 50
    assert d.sign_language == "NSL"


def test_all_ids_language_neutral_and_unique():
    d = build_dictionary()
    ids = [s.sign_id for s in d.signs]
    assert len(ids) == len(set(ids)), "sign_ids must be unique"
    for sid in ids:
        assert sid.startswith("NSL_") and sid[4:].isdigit()


def test_every_sign_has_both_labels():
    d = build_dictionary()
    for s in d.signs:
        assert s.labels.en and s.labels.ne, f"{s.sign_id} missing a label"


def test_bad_sign_id_rejected():
    from signbridge.schema import Labels, Parameters, Sign

    with pytest.raises(ValueError):
        Sign(
            sign_id="HELLO",  # not language-neutral
            labels=Labels(en="hello", ne="नमस्ते"),
            gloss_code="HELLO",
            parameters=Parameters(
                handshape="flat_B", location="chest", movement="static", orientation="in"
            ),
        )
