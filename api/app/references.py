"""Reference-sequence loader for DTW scoring.

References live in api/models/references/<sign>.npy (built by ml/scripts/build_references.py,
gitignored). If none are present, scoring endpoints report unavailable and the tutor falls
back to self-rating.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

REF_DIR = Path(__file__).resolve().parent.parent / "models" / "references"


def available() -> bool:
    return REF_DIR.exists() and any(REF_DIR.glob("*.npy"))


@lru_cache(maxsize=256)
def load_reference(sign_id: str) -> np.ndarray | None:
    path = REF_DIR / f"{sign_id}.npy"
    if not path.exists():
        return None
    return np.load(path).astype(np.float32)


def synthesize_attempt(reference: np.ndarray, noise: float, seed: int | None = None) -> np.ndarray:
    """A plausible learner attempt = reference + noise. Lets the DTW+Critique path run
    end-to-end without a webcam. Higher noise -> lower score."""
    rng = np.random.default_rng(seed)
    return (reference + rng.normal(0, noise, reference.shape).astype(np.float32)).astype(np.float32)
