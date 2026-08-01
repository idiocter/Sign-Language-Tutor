"""Evaluation surface (Phase 5): model metrics + native-signer intelligibility ratings.

PROJECT_PLAN.md Phase 5: the numbers that matter are signer-independent recognition
accuracy and **avatar intelligibility rated by native signers**. This exposes the model
metrics and collects intelligibility ratings (which must come from deaf NSL signers).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..inference_engine import FINGERSPELL_DIR, MODEL_DIR
from ..models import IntelligibilityRating

router = APIRouter(prefix="/eval", tags=["eval"])


def _metrics(model_dir) -> dict | None:
    path = model_dir / "metrics.json"
    return json.loads(path.read_text()) if path.exists() else None


class RatingIn(BaseModel):
    sign_id: str
    score: int = Field(..., ge=1, le=5)
    comment: str | None = None


@router.get("/models")
def model_metrics() -> dict:
    """Reported metrics for the recognition + fingerspelling models."""
    return {
        "recognition": _metrics(MODEL_DIR),
        "fingerspelling": _metrics(FINGERSPELL_DIR),
    }


@router.post("/rating")
def submit_rating(payload: RatingIn, db: Session = Depends(get_db)) -> dict:
    if not payload.sign_id:
        raise HTTPException(422, "sign_id required")
    r = IntelligibilityRating(sign_id=payload.sign_id, score=payload.score, comment=payload.comment)
    db.add(r)
    db.commit()
    return {"ok": True}


@router.get("/ratings/summary")
def ratings_summary(db: Session = Depends(get_db)) -> dict:
    """Average intelligibility and count. The Phase 2/5 gate is mean ≥ 4/5."""
    row = db.execute(
        select(func.count(IntelligibilityRating.id), func.avg(IntelligibilityRating.score))
    ).one()
    count, avg = row[0], row[1]
    per_sign = db.execute(
        select(
            IntelligibilityRating.sign_id,
            func.count(IntelligibilityRating.id),
            func.avg(IntelligibilityRating.score),
        ).group_by(IntelligibilityRating.sign_id)
    ).all()
    return {
        "count": count,
        "mean_score": round(float(avg), 2) if avg is not None else None,
        "passes_gate": bool(avg is not None and float(avg) >= 4.0),
        "per_sign": [
            {"sign_id": s, "count": c, "mean": round(float(a), 2)} for s, c, a in per_sign
        ],
    }
