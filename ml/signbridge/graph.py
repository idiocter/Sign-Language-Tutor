"""Skeleton graph for ST-GCN — torch-free so it's testable without the full extra.

Builds the joint adjacency from real MediaPipe hand + pose connections over the
NUM_LANDMARKS joints (pose, left hand, right hand, face).
"""

from __future__ import annotations

import numpy as np

from .config import FACE_PTS, HAND_PTS, NUM_LANDMARKS, POSE_PTS

_LH0 = POSE_PTS
_RH0 = POSE_PTS + HAND_PTS
_FACE0 = POSE_PTS + 2 * HAND_PTS

# MediaPipe hand bone connections (21 joints).
HAND_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17), (0, 5), (0, 17),
]

# MediaPipe pose connections (upper body — the part that matters for signing).
POSE_EDGES = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (15, 17), (16, 18),
    (0, 11), (0, 12),
]


def skeleton_edges() -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = list(POSE_EDGES)
    for a, b in HAND_EDGES:
        edges.append((_LH0 + a, _LH0 + b))
        edges.append((_RH0 + a, _RH0 + b))
    edges.append((15, _LH0))  # left wrist -> left hand root
    edges.append((16, _RH0))  # right wrist -> right hand root
    for i in range(FACE_PTS - 1):  # chain face points so they're not isolated
        edges.append((_FACE0 + i, _FACE0 + i + 1))
    return edges


def skeleton_adjacency() -> np.ndarray:
    """Symmetric normalized adjacency  D^-1/2 (A + I) D^-1/2  over NUM_LANDMARKS joints."""
    v = NUM_LANDMARKS
    a = np.eye(v, dtype=np.float32)
    for i, j in skeleton_edges():
        if 0 <= i < v and 0 <= j < v:
            a[i, j] = a[j, i] = 1.0
    deg = a.sum(1)
    dinv = np.diag((deg + 1e-6) ** -0.5)
    return (dinv @ a @ dinv).astype(np.float32)
