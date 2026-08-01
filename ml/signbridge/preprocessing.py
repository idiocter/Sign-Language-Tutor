"""Preprocessing: normalization, augmentation, and the signer-independent split.

The one failure mode PROJECT_PLAN.md calls out by name:

    Splitting by clip instead of signer inflates accuracy 15–25 points and the model
    collapses on real users.

So the split here is **by signer**. A signer's clips are never spread across train and
test. :func:`split_by_signer` enforces that; splitting by clip is not offered as an option.

Filenames follow the capture tool's convention::

    {sign_id}__{signer_id}__{timestamp}.npy      e.g. NSL_0001__S03__20260731_140212.npy
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import (
    DIMS,
    LEFT_SHOULDER,
    NUM_LANDMARKS,
    RAW_DIR,
    RIGHT_SHOULDER,
    SEQ_LEN,
)

_NAME_RE = re.compile(r"^(?P<sign>NSL_\d{4})__(?P<signer>[^_]+)__(?P<stamp>\d{8}_\d{6})$")


@dataclass(frozen=True)
class Sample:
    path: Path
    sign_id: str
    signer_id: str

    @classmethod
    def from_path(cls, path: Path) -> "Sample | None":
        m = _NAME_RE.match(path.stem)
        if not m:
            return None
        return cls(path=path, sign_id=m["sign"], signer_id=m["signer"])


def discover(raw_dir: Path | str = RAW_DIR) -> list[Sample]:
    """Find every ``.npy`` take under ``raw_dir`` and parse sign/signer from its name."""
    root = Path(raw_dir)
    out: list[Sample] = []
    for p in sorted(root.rglob("*.npy")):
        s = Sample.from_path(p)
        if s is not None:
            out.append(s)
    return out


# --- Normalization ----------------------------------------------------------

def normalize(seq: np.ndarray) -> np.ndarray:
    """Center on the shoulder midpoint and scale by shoulder width.

    The single most important preprocessing step: without it the model learns how far the
    signer sat from the camera, not the sign. ``seq`` is ``(frames, FEATURE_DIM)``.
    """
    out = seq.copy().reshape(seq.shape[0], NUM_LANDMARKS, DIMS)
    l_sh, r_sh = out[:, LEFT_SHOULDER, :2], out[:, RIGHT_SHOULDER, :2]
    center = (l_sh + r_sh) / 2.0
    width = np.linalg.norm(l_sh - r_sh, axis=1, keepdims=True)
    width = np.where(width < 1e-6, 1.0, width)

    out[:, :, :2] -= center[:, None, :]
    out[:, :, :2] /= width[:, None, :]
    out[:, :, 2] /= width  # depth scaled the same way
    return out.reshape(seq.shape[0], -1)


def resample(seq: np.ndarray, target: int = SEQ_LEN) -> np.ndarray:
    """Linear interpolation to a fixed frame count. Signs vary in duration."""
    if len(seq) == target:
        return seq.astype(np.float32)
    idx_old = np.linspace(0, len(seq) - 1, len(seq))
    idx_new = np.linspace(0, len(seq) - 1, target)
    return np.stack(
        [np.interp(idx_new, idx_old, seq[:, c]) for c in range(seq.shape[1])],
        axis=1,
    ).astype(np.float32)


# --- Augmentation -----------------------------------------------------------
# Applied to landmark coordinates, not pixels. Keep augmentation mild — sign phonology is
# sensitive to location and orientation, so aggressive spatial jitter destroys the label.

def augment(seq: np.ndarray, *, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng()
    out = seq.copy().reshape(seq.shape[0], NUM_LANDMARKS, DIMS)

    # small isotropic scale (± 5%)
    out[:, :, :2] *= rng.uniform(0.95, 1.05)
    # small 2D translation
    out[:, :, :2] += rng.uniform(-0.05, 0.05, size=(1, 1, 2))
    # small in-plane rotation (± 8 degrees)
    theta = np.deg2rad(rng.uniform(-8, 8))
    c, s = np.cos(theta), np.sin(theta)
    x, y = out[:, :, 0].copy(), out[:, :, 1].copy()
    out[:, :, 0] = c * x - s * y
    out[:, :, 1] = s * x + c * y
    # per-frame Gaussian jitter
    out += rng.normal(0, 0.003, size=out.shape)
    return out.reshape(seq.shape[0], -1).astype(np.float32)


# --- Signer-independent split ----------------------------------------------

@dataclass
class Split:
    train: list[Sample]
    val: list[Sample]
    test: list[Sample]

    def signer_sets(self) -> dict[str, set[str]]:
        return {
            "train": {s.signer_id for s in self.train},
            "val": {s.signer_id for s in self.val},
            "test": {s.signer_id for s in self.test},
        }


def split_by_signer(
    samples: list[Sample],
    *,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    seed: int = 42,
) -> Split:
    """Partition *signers* (not clips) into train/val/test.

    Guarantees no signer appears in more than one split — the only split that yields an
    honest estimate of accuracy on unseen users.
    """
    signers = sorted({s.signer_id for s in samples})
    if len(signers) < 3:
        raise ValueError(
            f"need at least 3 distinct signers for a signer-split, got {len(signers)}: "
            f"{signers}. Collect more signers before training (plan: 5+ per sign)."
        )
    rng = random.Random(seed)
    rng.shuffle(signers)

    n = len(signers)
    n_test = max(1, round(n * test_frac))
    n_val = max(1, round(n * val_frac))
    test_signers = set(signers[:n_test])
    val_signers = set(signers[n_test : n_test + n_val])

    def bucket(s: Sample) -> str:
        if s.signer_id in test_signers:
            return "test"
        if s.signer_id in val_signers:
            return "val"
        return "train"

    split = Split(train=[], val=[], test=[])
    for s in samples:
        getattr(split, bucket(s)).append(s)
    _assert_disjoint(split)
    return split


def _assert_disjoint(split: Split) -> None:
    sets = split.signer_sets()
    if sets["train"] & sets["test"] or sets["train"] & sets["val"] or sets["val"] & sets["test"]:
        raise AssertionError("signer leaked across splits — this invalidates the metric")
