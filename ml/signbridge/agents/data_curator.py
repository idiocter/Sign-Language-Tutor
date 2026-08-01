"""Data Curator agent — quality-flags and dedupes submitted landmark takes.

Not language-aware. Operates on landmark statistics only. Flags takes that would poison
training: too short, near-static (no movement), missing both hands, or near-duplicates of
another take by the same signer. This is the automated first pass before a human reviews.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import DIMS, HAND_PTS, NUM_LANDMARKS, POSE_PTS, SEQ_LEN

_LH0 = POSE_PTS
_RH0 = POSE_PTS + HAND_PTS


@dataclass
class QualityReport:
    key: str                       # e.g. filename or sample id
    flags: list[str] = field(default_factory=list)
    duplicate_of: str | None = None

    @property
    def ok(self) -> bool:
        return not self.flags and self.duplicate_of is None


def _pooled(seq: np.ndarray) -> np.ndarray:
    return np.concatenate([seq.mean(axis=0), seq.std(axis=0)])


def _hands_present(seq: np.ndarray) -> bool:
    frames = seq.reshape(seq.shape[0], NUM_LANDMARKS, DIMS)
    lh = frames[:, _LH0 : _LH0 + HAND_PTS]
    rh = frames[:, _RH0 : _RH0 + HAND_PTS]
    # A hand recorded as all-zeros (capture tool fills missing hands with zeros) is absent.
    return bool(np.any(np.abs(lh) > 1e-6) or np.any(np.abs(rh) > 1e-6))


class DataCuratorAgent:
    name = "data_curator"
    language_aware = False

    def __init__(self, min_frames: int = 10, static_std: float = 1e-3, dup_cos: float = 0.999):
        self.min_frames = min_frames
        self.static_std = static_std
        self.dup_cos = dup_cos

    def run(self, takes: list[tuple[str, np.ndarray]], ctx=None) -> list[QualityReport]:
        """takes: list of (key, sequence[frames, FEATURE_DIM])."""
        reports: list[QualityReport] = []
        pooled: list[tuple[str, np.ndarray]] = []

        for key, seq in takes:
            r = QualityReport(key=key)
            if seq.shape[0] < self.min_frames:
                r.flags.append("too_short")
            if float(seq.std()) < self.static_std:
                r.flags.append("near_static")
            if not _hands_present(seq):
                r.flags.append("no_hands")

            v = _pooled(seq)
            for other_key, other_v in pooled:
                denom = np.linalg.norm(v) * np.linalg.norm(other_v)
                cos = float(v @ other_v / denom) if denom > 1e-9 else 0.0
                if cos > self.dup_cos:
                    r.duplicate_of = other_key
                    break
            pooled.append((key, v))
            reports.append(r)
        return reports
