"""Recognition inference: status, predict, demo, and a streaming WebSocket.

Primary inference runs **in-browser** (onnxruntime-web) so video never leaves the device.
These endpoints are the server-side path: model status, direct prediction from pooled
features, a self-contained demo (synthesize an attempt for a sign, then recognize it), and
a WebSocket fallback for clients without WebGPU.

The model here is the interim linear classifier trained on synthetic data
(ml/scripts/train_lite.py). Swap in the real Transformer's ONNX export when trained.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..inference_engine import get_engine

router = APIRouter(prefix="/inference", tags=["inference"])


class PredictIn(BaseModel):
    features: list[float] = Field(..., description="pooled feature vector (mean++std)")
    top_k: int = 3


class Prediction(BaseModel):
    sign_id: str
    confidence: float


class PredictOut(BaseModel):
    predictions: list[Prediction]


class DemoOut(BaseModel):
    target: str
    predicted: str
    correct: bool
    predictions: list[Prediction]


@router.get("/status")
def status() -> dict:
    e = get_engine()
    return {
        "ready": e.ready,
        "num_classes": len(e.labels),
        "metrics": e.metrics,
        "has_prototypes": bool(e.prototypes),
    }


@router.post("/predict", response_model=PredictOut)
def predict(payload: PredictIn) -> PredictOut:
    e = get_engine()
    if not e.ready:
        raise HTTPException(503, "recognition model not loaded — run ml/scripts/train_lite.py")
    return PredictOut(predictions=[Prediction(**p) for p in e.predict(payload.features, payload.top_k)])


@router.post("/demo", response_model=DemoOut)
def demo(sign_id: str) -> DemoOut:
    """Synthesize an attempt for ``sign_id`` and recognize it — a closed-loop demo."""
    e = get_engine()
    if not e.ready:
        raise HTTPException(503, "recognition model not loaded — run ml/scripts/train_lite.py")
    try:
        feats = e.sample_features(sign_id)
    except KeyError:
        raise HTTPException(404, f"no prototype for {sign_id} (not in the trained model)")
    preds = e.predict(feats, top_k=3)
    predicted = preds[0]["sign_id"] if preds else ""
    return DemoOut(
        target=sign_id,
        predicted=predicted,
        correct=predicted == sign_id,
        predictions=[Prediction(**p) for p in preds],
    )


class SampleOut(BaseModel):
    sign_id: str
    features: list[float]


@router.get("/sample", response_model=SampleOut)
def sample(sign_id: str) -> SampleOut:
    """Return a synthesized pooled-feature attempt for a sign, so the browser can run
    inference locally (onnxruntime-web) without a webcam or downloaded MediaPipe models."""
    e = get_engine()
    if not e.ready:
        raise HTTPException(503, "recognition model not loaded — run ml/scripts/train_lite.py")
    try:
        return SampleOut(sign_id=sign_id, features=e.sample_features(sign_id))
    except KeyError:
        raise HTTPException(404, f"no prototype for {sign_id}")


@router.websocket("/ws")
async def inference_ws(ws: WebSocket) -> None:
    """client -> {"features": [...]}  ;  server -> {predictions:[...], ready:bool}"""
    await ws.accept()
    e = get_engine()
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            feats = msg.get("features")
            preds = e.predict(feats, top_k=3) if (e.ready and feats) else []
            await ws.send_json({"ready": e.ready, "predictions": preds})
    except WebSocketDisconnect:
        return
