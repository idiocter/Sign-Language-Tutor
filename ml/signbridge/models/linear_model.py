"""Interim recognition model: softmax classifier over pooled landmark features.

This is **not** the production model — that is the Transformer encoder in
``sign_transformer.py``, which needs real NSL data and a GPU. This linear model exists so
the whole Phase 1 loop (train → export ONNX → in-browser inference → live demo) actually
runs *today*, on synthetic data, with only numpy + onnx (no torch).

Features: each landmark sequence ``(frames, FEATURE_DIM)`` is temporally pooled to a fixed
``mean ++ std`` vector of length ``2 * FEATURE_DIM``. Movement shows up in the std term.
The classifier is plain multinomial logistic regression trained with gradient descent.

When real data arrives, keep this as the fast baseline and promote the Transformer.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..config import FEATURE_DIM

INPUT_DIM = 2 * FEATURE_DIM  # mean ++ std pooling


def pool_features(seq: np.ndarray) -> np.ndarray:
    """Temporal mean++std pooling of a ``(frames, FEATURE_DIM)`` sequence."""
    seq = np.asarray(seq, dtype=np.float32)
    return np.concatenate([seq.mean(axis=0), seq.std(axis=0)]).astype(np.float32)


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class LinearSignClassifier:
    """Multinomial logistic regression with standardized inputs.

    ``input_dim`` defaults to the pooled sign-feature size (``2 * FEATURE_DIM``) but can be
    any value — the fingerspelling model reuses this with single-frame hand features.
    """

    def __init__(self, labels: list[str], input_dim: int = INPUT_DIM):
        self.labels = labels
        self.input_dim = input_dim
        self.mean = np.zeros(input_dim, dtype=np.float32)
        self.scale = np.ones(input_dim, dtype=np.float32)
        self.W = np.zeros((input_dim, len(labels)), dtype=np.float32)
        self.b = np.zeros(len(labels), dtype=np.float32)

    # --- training -----------------------------------------------------------

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        epochs: int = 300,
        lr: float = 0.5,
        l2: float = 1e-4,
        seed: int = 0,
    ) -> "LinearSignClassifier":
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.int64)
        self.mean = X.mean(axis=0)
        self.scale = X.std(axis=0) + 1e-6
        Xs = (X - self.mean) / self.scale

        n, c = X.shape[0], len(self.labels)
        rng = np.random.default_rng(seed)
        self.W = (rng.normal(0, 0.01, (self.input_dim, c))).astype(np.float32)
        self.b = np.zeros(c, dtype=np.float32)
        Y = np.eye(c, dtype=np.float32)[y]

        for _ in range(epochs):
            probs = _softmax(Xs @ self.W + self.b)
            grad = probs - Y
            gW = Xs.T @ grad / n + l2 * self.W
            gb = grad.mean(axis=0)
            self.W -= lr * gW
            self.b -= lr * gb
        return self

    # --- inference ----------------------------------------------------------

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Xs = (np.asarray(X, dtype=np.float32) - self.mean) / self.scale
        return _softmax(Xs @ self.W + self.b)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        return float((self.predict(X) == np.asarray(y)).mean())

    # --- ONNX export --------------------------------------------------------

    def to_onnx(self, path: Path | str) -> None:
        """Emit an ONNX graph runnable by onnxruntime and onnxruntime-web.

        Folds standardization into the linear layer so the graph is just
        MatMul → Add → Softmax and the client sends raw pooled features.
        """
        from onnx import TensorProto, helper, numpy_helper, save

        # Fold (x - mean)/scale @ W + b  ->  x @ W' + b'
        W_eff = (self.W.T / self.scale).T.astype(np.float32)
        b_eff = (self.b - (self.mean / self.scale) @ self.W).astype(np.float32)

        W_init = numpy_helper.from_array(W_eff, name="W")
        b_init = numpy_helper.from_array(b_eff, name="b")

        inp = helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, self.input_dim])
        out = helper.make_tensor_value_info(
            "probs", TensorProto.FLOAT, [1, len(self.labels)]
        )
        nodes = [
            helper.make_node("MatMul", ["features", "W"], ["mm"]),
            helper.make_node("Add", ["mm", "b"], ["logits"]),
            helper.make_node("Softmax", ["logits"], ["probs"], axis=1),
        ]
        graph = helper.make_graph(nodes, "sign_linear", [inp], [out], [W_init, b_init])
        model = helper.make_model(
            graph, opset_imports=[helper.make_opsetid("", 13)], producer_name="signbridge"
        )
        model.doc_string = "SignBridge interim linear sign classifier (synthetic data)"
        save(model, str(path))

    def save_labels(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps({"labels": self.labels}, indent=2))
