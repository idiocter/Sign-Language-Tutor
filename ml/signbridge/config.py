"""Single source of truth for the landmark feature layout.

Every stage of the pipeline — capture, preprocessing, dataset, model — must agree on
exactly which landmarks make up a frame and in what order. Defining it once here prevents
the classic bug where the capture tool and the model disagree on feature dimension.
"""

from __future__ import annotations

from pathlib import Path

# --- Paths ------------------------------------------------------------------
ML_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ML_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
REFS_DIR = DATA_DIR / "refs"
SCHEMA_PATH = DATA_DIR / "sign_schema.json"
VOCAB_PATH = DATA_DIR / "vocabulary.csv"
DICTIONARY_PATH = DATA_DIR / "sign_dictionary.json"

# --- Sequence shape ---------------------------------------------------------
SEQ_LEN = 60            # frames per sample (~2s at 30fps)
DIMS = 3                # x, y, z per landmark

# --- Landmark counts (MediaPipe Holistic) -----------------------------------
POSE_PTS = 33
HAND_PTS = 21           # per hand; two hands -> 42

# Face mesh indices carrying non-manual grammar: brows, eyes, mouth, jaw anchors.
# The full 478-point mesh is mostly redundant surface detail and bloats the model.
FACE_SUBSET = [
    # eyebrows
    70, 63, 105, 66, 107, 336, 296, 334, 293, 300,
    # eyes
    33, 133, 160, 159, 158, 144, 145, 153,
    362, 263, 387, 386, 385, 373, 374, 380,
    # outer lips
    61, 291, 39, 181, 0, 17, 269, 405, 84, 314,
    78, 308, 13, 14, 82, 87, 312, 317,
    # inner lips + mouth corners
    95, 88, 178, 87, 14, 317, 402, 318, 324,
    # nose + jaw anchors
    1, 4, 5, 195, 197, 6, 168, 8,
    152, 148, 176, 149, 150, 136, 172, 58, 132,
]
FACE_PTS = len(FACE_SUBSET)

# Ordered layout of a single flattened frame vector.
# Order is fixed: pose, left hand, right hand, face.
LANDMARK_LAYOUT = (
    ("pose", POSE_PTS),
    ("left_hand", HAND_PTS),
    ("right_hand", HAND_PTS),
    ("face", FACE_PTS),
)
NUM_LANDMARKS = sum(n for _, n in LANDMARK_LAYOUT)
FEATURE_DIM = NUM_LANDMARKS * DIMS

# Pose landmark indices used for shoulder-normalization (MediaPipe pose).
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
