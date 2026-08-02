"""ST-GCN: spatial-temporal graph convolution over the landmark skeleton.

TECH_STACK.md Layer 2 lists ST-GCN as the alternative to the Transformer — it exploits the
skeleton graph topology (which joints are physically connected) instead of treating the
landmarks as an unordered vector. Try it if the Transformer plateaus.

Input is the same normalized landmark sequence as the Transformer,
``(batch, SEQ_LEN, FEATURE_DIM)``; internally reshaped to ``(batch, C=3, T, V)`` over the
V=NUM_LANDMARKS joints. The adjacency is built from real MediaPipe hand + pose connections.

Requires the ``full`` extra (torch). Kept out of the foundation import path.
"""

from __future__ import annotations

import torch
from torch import nn

from ..config import DIMS, NUM_LANDMARKS, SEQ_LEN
from ..graph import skeleton_adjacency


def build_adjacency() -> torch.Tensor:
    """Normalized skeleton adjacency as a torch tensor (graph logic lives in graph.py)."""
    return torch.from_numpy(skeleton_adjacency())


class STGCNBlock(nn.Module):
    """Spatial graph conv + temporal conv, with a residual connection."""

    def __init__(self, in_c: int, out_c: int, t_kernel: int = 9, stride: int = 1):
        super().__init__()
        self.gconv = nn.Conv2d(in_c, out_c, kernel_size=1)  # 1x1 over channels
        pad = (t_kernel - 1) // 2
        self.tconv = nn.Sequential(
            nn.BatchNorm2d(out_c),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_c, out_c, kernel_size=(t_kernel, 1), stride=(stride, 1), padding=(pad, 0)),
            nn.BatchNorm2d(out_c),
        )
        self.residual = (
            nn.Identity()
            if in_c == out_c and stride == 1
            else nn.Conv2d(in_c, out_c, kernel_size=1, stride=(stride, 1))
        )
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        # x: (N, C, T, V). Spatial aggregation: mix joints via the adjacency.
        res = self.residual(x)
        y = self.gconv(x)
        y = torch.einsum("nctv,vw->nctw", y, adj)  # graph conv
        y = self.tconv(y)
        return self.relu(y + res)


class STGCN(nn.Module):
    def __init__(self, num_classes: int, in_channels: int = DIMS):
        super().__init__()
        self.register_buffer("adj", build_adjacency())
        self.data_bn = nn.BatchNorm1d(in_channels * NUM_LANDMARKS)
        self.blocks = nn.ModuleList(
            [
                STGCNBlock(in_channels, 64),
                STGCNBlock(64, 64),
                STGCNBlock(64, 128, stride=2),
                STGCNBlock(128, 128),
                STGCNBlock(128, 256, stride=2),
                STGCNBlock(256, 256),
            ]
        )
        self.head = nn.Linear(256, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (N, T, FEATURE_DIM) -> (N, C, T, V)
        n, t, _ = x.shape
        x = x.view(n, t, NUM_LANDMARKS, DIMS)
        x = self.data_bn(x.permute(0, 2, 3, 1).reshape(n, -1, t)).reshape(
            n, NUM_LANDMARKS, DIMS, t
        )
        x = x.permute(0, 2, 3, 1).contiguous()  # (N, C, T, V)
        for block in self.blocks:
            x = block(x, self.adj)
        x = x.mean(dim=(2, 3))  # global average pool over time + joints
        return self.head(x)

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


def _self_test() -> None:  # pragma: no cover - needs torch
    m = STGCN(num_classes=60)
    y = m(torch.randn(2, SEQ_LEN, NUM_LANDMARKS * DIMS))
    assert y.shape == (2, 60), y.shape
