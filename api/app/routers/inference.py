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

from signbridge.fingerspelling import spellable
from signbridge.transliterate import build_lexicon, to_devanagari

from ..inference_engine import get_engine, get_fingerspell_engine

router = APIRouter(prefix="/inference", tags=["inference"])
_LEXICON = build_lexicon()


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


# --- Fingerspelling (Phase 1.5) ---------------------------------------------


class SpellCharOut(BaseModel):
    target_char: str
    target_roman: str
    predicted_char: str
    correct: bool
    confidence: float


class SpellOut(BaseModel):
    input: str
    devanagari: str
    chars: list[SpellCharOut]
    accuracy: float


@router.get("/fingerspell/status")
def fingerspell_status() -> dict:
    e = get_fingerspell_engine()
    return {"ready": e.ready, "num_classes": len(e.labels), "metrics": e.metrics}


@router.get("/fingerspell/spell", response_model=SpellOut)
def fingerspell(word: str) -> SpellOut:
    """Transliterate a (Romanized or Devanagari) word, fingerspell each character, and
    recognize each handshape — a closed-loop demo of the manual alphabet."""
    e = get_fingerspell_engine()
    if not e.ready:
        raise HTTPException(503, "fingerspelling model not loaded — run train_fingerspelling.py")
    deva = to_devanagari(word, lexicon=_LEXICON)
    chars = spellable(deva)
    out: list[SpellCharOut] = []
    hits = 0
    roman_by_char = dict(zip(e.labels, e.romans)) if e.romans else {}
    for ch in chars:
        try:
            feats = e.sample_features(ch)
        except KeyError:
            continue
        preds = e.predict(feats, top_k=1)
        pred = preds[0]["sign_id"] if preds else ""
        correct = pred == ch
        hits += int(correct)
        out.append(
            SpellCharOut(
                target_char=ch,
                target_roman=roman_by_char.get(ch, ""),
                predicted_char=pred,
                correct=correct,
                confidence=preds[0]["confidence"] if preds else 0.0,
            )
        )
    acc = hits / len(out) if out else 0.0
    return SpellOut(input=word, devanagari=deva, chars=out, accuracy=round(acc, 3))


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
