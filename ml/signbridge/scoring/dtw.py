"""DTW scoring on normalized joint angles, decomposed by sign parameter.

TECH_STACK.md Layer 6:

    Decomposing error by sign parameter is what turns a score into teaching. "72% match"
    is useless; "handshape correct, movement amplitude too small" is a lesson.

So we do **not** DTW raw coordinates. We derive interpretable features per frame —
handshape (finger joint angles), orientation (palm normal), location (hand position
relative to the body), movement (wrist trajectory) — align learner vs. reference with
DTW, and report an error per parameter that maps straight onto the schema's
``parameters`` block and the Critique agent's feedback.

Pure-Python + numpy + fastdtw: part of the ``foundation`` extra, no torch needed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from ..config import DIMS, HAND_PTS, NUM_LANDMARKS, POSE_PTS

# Offsets into a flattened, reshaped (NUM_LANDMARKS, 3) frame.
_POSE0 = 0
_LH0 = POSE_PTS
_RH0 = POSE_PTS + HAND_PTS

# MediaPipe hand landmark indices (within a single 21-point hand).
_FINGERS = {
    "thumb": [1, 2, 3, 4],
    "index": [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring": [13, 14, 15, 16],
    "pinky": [17, 18, 19, 20],
}
_WRIST = 0
_INDEX_MCP = 5
_PINKY_MCP = 17

# MediaPipe pose shoulders (already used for normalization upstream).
_L_SHOULDER, _R_SHOULDER = 11, 12


def _frames(seq: np.ndarray) -> np.ndarray:
    return seq.reshape(seq.shape[0], NUM_LANDMARKS, DIMS)


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle ABC at vertex b, in radians."""
    ba, bc = a - b, c - b
    nba, nbc = np.linalg.norm(ba), np.linalg.norm(bc)
    if nba < 1e-8 or nbc < 1e-8:
        return 0.0
    cos = np.clip(np.dot(ba, bc) / (nba * nbc), -1.0, 1.0)
    return float(np.arccos(cos))


def _hand(frame: np.ndarray, base: int) -> np.ndarray:
    return frame[base : base + HAND_PTS]


# --- Per-frame feature extractors -------------------------------------------

def _handshape_features(frame: np.ndarray) -> np.ndarray:
    """Per-finger curl as an extension ratio for both hands.

    curl = 1 - |tip - mcp| / (total bone length). ~0 when the finger is straight, ~1 when
    fully curled. This is far more stable under landmark noise than raw joint angles (which
    blow up near-degenerate triangles), so the score reflects real handshape differences
    rather than sensor jitter.
    """
    feats: list[float] = []
    for base in (_LH0, _RH0):
        hand = _hand(frame, base)
        for joints in _FINGERS.values():
            mcp, tip = hand[joints[0]], hand[joints[3]]
            bone = sum(
                float(np.linalg.norm(hand[joints[k + 1]] - hand[joints[k]])) for k in range(3)
            )
            straight = float(np.linalg.norm(tip - mcp))
            curl = 1.0 - straight / bone if bone > 1e-6 else 0.0
            feats.append(max(0.0, min(1.0, curl)))
    return np.asarray(feats, dtype=np.float32)


# Palm points (wrist + the four finger MCPs) for a stable plane fit.
_PALM_PTS = [_WRIST, _INDEX_MCP, 9, 13, _PINKY_MCP]


def _orientation_features(frame: np.ndarray) -> np.ndarray:
    """Palm-normal direction for each hand, from an SVD plane fit over the palm points.

    A least-squares normal over five palm points is far steadier than a single
    wrist→index × wrist→pinky cross product, which flips/jitters under noise.
    """
    feats: list[float] = []
    for base in (_LH0, _RH0):
        hand = _hand(frame, base)
        pts = hand[_PALM_PTS]
        centered = pts - pts.mean(axis=0)
        # normal = singular vector with the smallest singular value
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            normal = vh[-1]
        except np.linalg.LinAlgError:  # pragma: no cover
            normal = np.zeros(3, dtype=np.float32)
        # Fix sign ambiguity: align to the coarse cross-product normal so it's consistent.
        ref = np.cross(hand[_INDEX_MCP] - hand[_WRIST], hand[_PINKY_MCP] - hand[_WRIST])
        if float(np.dot(normal, ref)) < 0:
            normal = -normal
        n = np.linalg.norm(normal)
        feats.extend((normal / n) if n > 1e-8 else np.zeros(3))
    return np.asarray(feats, dtype=np.float32)


def _location_features(frame: np.ndarray) -> np.ndarray:
    """Wrist position relative to shoulder midpoint (already shoulder-normalized)."""
    pose = frame[_POSE0:_POSE0 + POSE_PTS]
    mid = (pose[_L_SHOULDER] + pose[_R_SHOULDER]) / 2.0
    feats: list[float] = []
    for base in (_LH0, _RH0):
        feats.extend(_hand(frame, base)[_WRIST] - mid)
    return np.asarray(feats, dtype=np.float32)


_EXTRACTORS = {
    "handshape": _handshape_features,
    "orientation": _orientation_features,
    "location": _location_features,
}


def _feature_sequence(seq: np.ndarray, name: str) -> np.ndarray:
    frames = _frames(seq)
    return np.stack([_EXTRACTORS[name](f) for f in frames])


def _dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Mean per-step Euclidean distance along the DTW alignment path."""
    try:
        from fastdtw import fastdtw
    except Exception as exc:  # pragma: no cover
        raise ImportError("fastdtw is required (install the 'foundation' extra)") from exc

    dist, path = fastdtw(a, b, dist=lambda x, y: float(np.linalg.norm(x - y)))
    return dist / max(len(path), 1)


def _movement_distance(learner: np.ndarray, reference: np.ndarray) -> float:
    """DTW over wrist trajectories — captures path shape and amplitude."""
    a = _feature_sequence(learner, "location")
    b = _feature_sequence(reference, "location")
    return _dtw_distance(a, b)


# --- Public API -------------------------------------------------------------

@dataclass
class ParameterErrors:
    handshape: float
    location: float
    movement: float
    orientation: float

    def worst(self) -> str:
        return max(asdict(self).items(), key=lambda kv: kv[1])[0]


@dataclass
class ScoreResult:
    overall: float                     # 0..100, higher is better
    parameters: ParameterErrors        # raw per-parameter DTW error (lower is better)
    feedback_target: str               # the parameter to correct first

    def as_dict(self) -> dict:
        return {
            "overall": self.overall,
            "parameters": asdict(self.parameters),
            "feedback_target": self.feedback_target,
        }


# Per-parameter weights + a global calibration so the 0–100 score lands in a useful range:
# a clean attempt (small sensor-level error) reads ~90, a sloppy one drops off smoothly, and
# a completely wrong sign is near zero. Handshape and location are trusted most; orientation
# (a fitted normal) is the noisiest signal so it's weighted down. Recalibrate against real
# reference/attempt pairs once collected.
_WEIGHTS = {"handshape": 1.4, "location": 1.3, "movement": 1.1, "orientation": 0.6}
_SCORE_SCALE = 0.42  # global slope of error -> score


def score_attempt(learner: np.ndarray, reference: np.ndarray) -> ScoreResult:
    """Compare a learner attempt against a reference sign.

    Both are ``(frames, FEATURE_DIM)`` normalized landmark sequences. Returns an overall
    0–100 score plus the per-parameter breakdown that the Critique agent turns into a
    specific, joint-level correction.
    """
    errors = ParameterErrors(
        handshape=_dtw_distance(
            _feature_sequence(learner, "handshape"), _feature_sequence(reference, "handshape")
        ),
        location=_dtw_distance(
            _feature_sequence(learner, "location"), _feature_sequence(reference, "location")
        ),
        movement=_movement_distance(learner, reference),
        orientation=_dtw_distance(
            _feature_sequence(learner, "orientation"),
            _feature_sequence(reference, "orientation"),
        ),
    )
    per_param = {k: _WEIGHTS[k] * v for k, v in asdict(errors).items()}
    weighted = sum(per_param.values())
    overall = float(100.0 * np.exp(-_SCORE_SCALE * weighted))  # monotonic: 0 error → 100
    # Correct first the parameter that costs the most score (weighted, not raw).
    feedback_target = max(per_param.items(), key=lambda kv: kv[1])[0]
    return ScoreResult(
        overall=round(overall, 1),
        parameters=errors,
        feedback_target=feedback_target,
    )
