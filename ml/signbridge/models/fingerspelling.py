"""Fingerspelling: static Devanagari manual-alphabet classifier (Phase 1.5).

A separate, simpler model from isolated-sign recognition: single-frame handshape
classification (~36 consonants + vowel signs), no temporal model. TECH_STACK.md picks
MobileNetV3 on a cropped hand region; exit criteria ≥90% top-1.

STUB: architecture wiring is here; training needs 100+ samples per character
(DOWNLOADS.md / PROJECT_PLAN.md Phase 1.5). Requires the ``full`` extra (torch).
"""

from __future__ import annotations

import torch
from torch import nn


class FingerspellingNet(nn.Module):
    """MobileNetV3-Small backbone + linear head over Devanagari characters."""

    def __init__(self, num_chars: int = 46):
        super().__init__()
        try:
            from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
        except Exception as exc:  # pragma: no cover
            raise ImportError("torchvision is required (install the 'full' extra)") from exc

        self.backbone = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
        in_features = self.backbone.classifier[-1].in_features
        self.backbone.classifier[-1] = nn.Linear(in_features, num_chars)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, 3, H, W) cropped hand
        return self.backbone(x)
