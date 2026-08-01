"""Isolated-sign recognition: a Transformer encoder over landmark sequences.

Per TECH_STACK.md Layer 2: ~5–10M params, trains on a single GPU / Colab. Input is a
normalized landmark sequence ``(batch, SEQ_LEN, FEATURE_DIM)``; output is class logits
over the sign vocabulary.

Pretraining path (PROJECT_PLAN.md Phase 1): pretrain on WLASL skeleton features, then
fine-tune on NSL. Skeleton features transfer across sign languages far better than pixels.

Requires the ``full`` extra (torch). Kept out of the foundation import path on purpose.
"""

from __future__ import annotations

import math

import torch
from torch import nn

from ..config import FEATURE_DIM, SEQ_LEN


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = SEQ_LEN):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, D)
        return x + self.pe[:, : x.size(1)]


class SignTransformer(nn.Module):
    """Landmark-sequence Transformer encoder classifier."""

    def __init__(
        self,
        num_classes: int,
        feature_dim: int = FEATURE_DIM,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 6,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.input_proj = nn.Linear(feature_dim, d_model)
        self.pos_enc = PositionalEncoding(d_model)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, d_model))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, num_classes)

    def forward(self, x: torch.Tensor, key_padding_mask: torch.Tensor | None = None):
        # x: (B, T, feature_dim). Prepend a CLS token; classify from its output.
        b = x.size(0)
        h = self.input_proj(x)
        cls = self.cls_token.expand(b, -1, -1)
        h = torch.cat([cls, h], dim=1)
        h = self.pos_enc(h)
        if key_padding_mask is not None:
            pad = torch.zeros(b, 1, dtype=torch.bool, device=x.device)
            key_padding_mask = torch.cat([pad, key_padding_mask], dim=1)
        h = self.encoder(h, src_key_padding_mask=key_padding_mask)
        return self.head(self.norm(h[:, 0]))

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


def export_onnx(model: SignTransformer, path: str, seq_len: int = SEQ_LEN) -> None:
    """Export to ONNX for in-browser inference (ONNX Runtime Web / WebGPU).

    Video never leaves the device — the whole point of browser inference (PROJECT_PLAN.md
    Phase 1 exit criteria).
    """
    model.eval()
    dummy = torch.randn(1, seq_len, FEATURE_DIM)
    torch.onnx.export(
        model,
        dummy,
        path,
        input_names=["landmarks"],
        output_names=["logits"],
        dynamic_axes={"landmarks": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
    )
