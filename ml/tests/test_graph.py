"""Skeleton graph adjacency for ST-GCN (torch-free part)."""

from __future__ import annotations

import numpy as np

from signbridge.config import NUM_LANDMARKS
from signbridge.graph import skeleton_adjacency, skeleton_edges


def test_edges_in_bounds():
    for i, j in skeleton_edges():
        assert 0 <= i < NUM_LANDMARKS and 0 <= j < NUM_LANDMARKS


def test_adjacency_shape_and_symmetry():
    a = skeleton_adjacency()
    assert a.shape == (NUM_LANDMARKS, NUM_LANDMARKS)
    assert np.allclose(a, a.T, atol=1e-6)  # symmetric


def test_adjacency_has_self_loops_and_connections():
    a = skeleton_adjacency()
    assert np.all(np.diag(a) > 0)  # every joint self-connected (A + I)
    # more than just the diagonal is populated (real skeleton edges exist)
    off_diag = a - np.diag(np.diag(a))
    assert np.count_nonzero(off_diag) > 0
