"""Preprocessing: normalization invariants and the signer-independent split."""

from __future__ import annotations

import numpy as np
import pytest

from signbridge.config import FEATURE_DIM, SEQ_LEN
from signbridge.preprocessing import (
    Sample,
    Split,
    augment,
    normalize,
    resample,
    split_by_signer,
)


def _fake_seq(frames: int = 40, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(frames, FEATURE_DIM)).astype(np.float32)


def test_resample_to_fixed_length():
    out = resample(_fake_seq(37), SEQ_LEN)
    assert out.shape == (SEQ_LEN, FEATURE_DIM)


def test_normalize_is_scale_and_shift_invariant():
    from signbridge.config import DIMS, NUM_LANDMARKS

    seq = _fake_seq()
    a = normalize(seq).reshape(seq.shape[0], NUM_LANDMARKS, DIMS)
    # Scaling and shifting the raw x,y (a further-away / off-center camera) must not change
    # the normalized x,y output — that is the whole point of shoulder normalization.
    shifted = seq.reshape(seq.shape[0], NUM_LANDMARKS, DIMS).copy()
    shifted[:, :, :2] = shifted[:, :, :2] * 2.0 + 0.3
    b = normalize(shifted.reshape(seq.shape[0], -1)).reshape(seq.shape[0], NUM_LANDMARKS, DIMS)
    assert np.allclose(a[:, :, :2], b[:, :, :2], atol=1e-4)


def test_augment_preserves_shape():
    seq = resample(_fake_seq(), SEQ_LEN)
    out = augment(seq, rng=np.random.default_rng(1))
    assert out.shape == seq.shape
    assert not np.allclose(out, seq)  # augmentation actually perturbs


def _samples() -> list[Sample]:
    from pathlib import Path

    out = []
    for signer in ["S01", "S02", "S03", "S04", "S05"]:
        for sign in ["NSL_0001", "NSL_0002"]:
            for k in range(3):
                p = Path(f"data/raw/{sign}/{sign}__{signer}__2026010{k}_120000.npy")
                out.append(Sample(path=p, sign_id=sign, signer_id=signer))
    return out


def test_split_is_signer_disjoint():
    split = split_by_signer(_samples(), seed=1)
    sets = split.signer_sets()
    assert not (sets["train"] & sets["test"])
    assert not (sets["train"] & sets["val"])
    assert not (sets["val"] & sets["test"])
    # every sample landed somewhere
    total = len(split.train) + len(split.val) + len(split.test)
    assert total == len(_samples())


def test_split_rejects_too_few_signers():
    from pathlib import Path

    tiny = [
        Sample(path=Path("x.npy"), sign_id="NSL_0001", signer_id="S01"),
        Sample(path=Path("y.npy"), sign_id="NSL_0001", signer_id="S02"),
    ]
    with pytest.raises(ValueError):
        split_by_signer(tiny)


def test_split_type():
    assert isinstance(split_by_signer(_samples()), Split)
