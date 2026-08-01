"""Torch dataset over collected landmark takes. Requires the ``full`` extra.

Pairs with :func:`signbridge.preprocessing.split_by_signer` so train/val/test are always
signer-disjoint. Optional on-the-fly augmentation for the training split only.
"""

from __future__ import annotations

import numpy as np

from .preprocessing import Sample, augment

try:  # torch is part of the `full` extra
    import torch
    from torch.utils.data import Dataset
except Exception as exc:  # pragma: no cover
    raise ImportError("signbridge.dataset requires torch (install the 'full' extra)") from exc


class LandmarkDataset(Dataset):
    """Yields ``(sequence[SEQ_LEN, FEATURE_DIM], label_index)`` tensors."""

    def __init__(self, samples: list[Sample], labels: list[str], *, train: bool = False):
        self.samples = samples
        self.labels = labels
        self.index = {sid: i for i, sid in enumerate(labels)}
        self.train = train

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, i: int):
        s = self.samples[i]
        seq = np.load(s.path).astype(np.float32)
        if self.train:
            seq = augment(seq)
        return torch.from_numpy(seq), self.index[s.sign_id]


def build_label_set(samples: list[Sample]) -> list[str]:
    return sorted({s.sign_id for s in samples})
