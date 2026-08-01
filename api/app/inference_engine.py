"""Loads the interim recognition model and serves predictions.

Model artifacts live in ``api/models/recognition/`` (produced by
``ml/scripts/train_lite.py``). If they're absent, the engine reports ``ready = False`` and
endpoints degrade gracefully instead of crashing — the app still runs before any model is
trained.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models"
MODEL_DIR = MODELS_ROOT / "recognition"
FINGERSPELL_DIR = MODELS_ROOT / "fingerspelling"


class InferenceEngine:
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = model_dir
        self.ready = False
        self.labels: list[str] = []
        self.romans: list[str] = []
        self.prototypes: dict[str, list[float]] = {}
        self.metrics: dict = {}
        self._sess = None
        self._input_name = ""
        self._load()

    def _load(self) -> None:
        model_path = self.model_dir / "model.onnx"
        if not model_path.exists():
            return
        try:
            import onnxruntime as ort

            self._sess = ort.InferenceSession(str(model_path))
            self._input_name = self._sess.get_inputs()[0].name
            labels_doc = json.loads((self.model_dir / "labels.json").read_text())
            self.labels = labels_doc["labels"]
            self.romans = labels_doc.get("romans", [])
            proto_path = self.model_dir / "prototypes.json"
            self.prototypes = json.loads(proto_path.read_text()) if proto_path.exists() else {}
            metrics_path = self.model_dir / "metrics.json"
            self.metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
            self.ready = True
        except Exception:  # pragma: no cover - missing/bad artifacts
            self.ready = False

    def predict(self, features: list[float], top_k: int = 3) -> list[dict]:
        if not self.ready or self._sess is None:
            return []
        x = np.asarray(features, dtype=np.float32)[None, :]
        probs = self._sess.run(None, {self._input_name: x})[0][0]
        order = np.argsort(probs)[::-1][:top_k]
        return [
            {"sign_id": self.labels[i], "confidence": float(probs[i])} for i in order
        ]

    def sample_features(self, sign_id: str, noise: float = 0.03, seed: int | None = None) -> list[float]:
        """Synthesize a plausible attempt for a sign from its stored prototype.

        Lets the demo exercise real inference without a webcam or downloaded models. Only
        available on the synthetic interim model (which ships prototypes).
        """
        if sign_id not in self.prototypes:
            raise KeyError(sign_id)
        rng = np.random.default_rng(seed)
        base = np.asarray(self.prototypes[sign_id], dtype=np.float32)
        return (base + rng.normal(0, noise, base.shape).astype(np.float32)).tolist()


@lru_cache(maxsize=1)
def get_engine() -> InferenceEngine:
    return InferenceEngine(MODEL_DIR)


@lru_cache(maxsize=1)
def get_fingerspell_engine() -> InferenceEngine:
    return InferenceEngine(FINGERSPELL_DIR)
