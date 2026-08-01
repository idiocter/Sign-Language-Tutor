"""Streaming recognition inference — WebSocket fallback path.

Primary inference runs **in-browser** (ONNX Runtime Web) so video never leaves the device
(PROJECT_PLAN.md Phase 1). This server endpoint is the fallback for clients that can't run
WebGPU: it receives normalized landmark frames and returns a predicted sign.

STUB: no trained weights exist yet, so this returns a deterministic placeholder prediction.
Wire `signbridge.models.sign_transformer.SignTransformer` + an ONNX/torch session here once
a model is trained. The message contract below is stable and safe to build the UI against.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from signbridge.config import SEQ_LEN

from .signs import _dictionary

router = APIRouter(tags=["inference"])


@router.websocket("/ws/inference")
async def inference_ws(ws: WebSocket) -> None:
    """Protocol:

    client -> {"frames": [[...FEATURE_DIM...], ...]}   # a window of normalized landmarks
    server -> {"sign_id", "label_en", "label_ne", "confidence", "stub": true}
    """
    await ws.accept()
    signs = _dictionary().signs
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            frames = msg.get("frames", [])
            # Placeholder: pick a sign deterministically from the window length so the UI
            # sees changing, well-formed responses. Replace with a real model forward pass.
            idx = (len(frames) or SEQ_LEN) % len(signs)
            s = signs[idx]
            await ws.send_json(
                {
                    "sign_id": s.sign_id,
                    "label_en": s.labels.en,
                    "label_ne": s.labels.ne,
                    "confidence": 0.0,
                    "stub": True,
                }
            )
    except WebSocketDisconnect:
        return
