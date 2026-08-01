"""
SignBridge — Phase 0 Capture Tool

Records normalized landmark sequences for building the NSL dataset.

Why normalized landmarks and not video:
  - ~200x smaller on disk
  - Model learns signs, not camera distance or clothing
  - Runs on CPU, no GPU needed for collection

Why signer_id is mandatory:
  Your train/test split MUST be by signer, not by clip. Splitting by clip
  inflates accuracy 15-25 points and the model collapses on real users.
  You cannot do a signer split if you didn't record who signed what.

Usage:
    python capture_tool.py --signer S01 --sign NSL_0001

Controls:
    SPACE   start / stop recording a take
    n       next sign in the queue
    d       delete the last take
    q       quit
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

# --- Config -----------------------------------------------------------------

SEQ_LEN = 60            # frames per sample (~2s at 30fps)
OUT_DIR = Path("data/raw")
HAND_PTS = 21
POSE_PTS = 33
FACE_KEY_PTS = 68       # subset of the 478 face mesh points

# Face mesh indices carrying non-manual grammar: brows, eyes, mouth outline.
# Full 478 points is mostly redundant surface detail and bloats your model.
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


class LandmarkCapture:
    def __init__(self, signer_id: str):
        self.signer_id = signer_id
        self.holistic = mp.solutions.holistic.Holistic(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1,
        )
        self.drawer = mp.solutions.drawing_utils

    def extract(self, results):
        """Pull landmarks into a flat feature vector for one frame."""
        def pts(landmark_list, n, dims=3):
            if landmark_list is None:
                return np.zeros(n * dims, dtype=np.float32)
            return np.array(
                [[lm.x, lm.y, lm.z][:dims] for lm in landmark_list.landmark],
                dtype=np.float32,
            ).flatten()

        pose = pts(results.pose_landmarks, POSE_PTS)
        lh = pts(results.left_hand_landmarks, HAND_PTS)
        rh = pts(results.right_hand_landmarks, HAND_PTS)

        if results.face_landmarks is None:
            face = np.zeros(len(FACE_SUBSET) * 3, dtype=np.float32)
        else:
            fl = results.face_landmarks.landmark
            face = np.array(
                [[fl[i].x, fl[i].y, fl[i].z] for i in FACE_SUBSET],
                dtype=np.float32,
            ).flatten()

        return np.concatenate([pose, lh, rh, face])

    @staticmethod
    def normalize(seq: np.ndarray) -> np.ndarray:
        """
        Center on shoulder midpoint, scale by shoulder width.

        This is the single most important preprocessing step. Without it your
        model learns how far the signer sat from the camera.
        """
        out = seq.copy().reshape(seq.shape[0], -1, 3)

        # MediaPipe pose: 11 = left shoulder, 12 = right shoulder
        l_sh, r_sh = out[:, 11, :2], out[:, 12, :2]
        center = (l_sh + r_sh) / 2.0
        width = np.linalg.norm(l_sh - r_sh, axis=1, keepdims=True)
        width = np.where(width < 1e-6, 1.0, width)

        out[:, :, :2] -= center[:, None, :]
        out[:, :, :2] /= width[:, None, :]
        out[:, :, 2] /= width  # depth scaled the same way

        return out.reshape(seq.shape[0], -1)

    @staticmethod
    def resample(seq: np.ndarray, target: int = SEQ_LEN) -> np.ndarray:
        """Linear interpolation to a fixed length. Signs vary in duration."""
        if len(seq) == target:
            return seq
        idx_old = np.linspace(0, len(seq) - 1, len(seq))
        idx_new = np.linspace(0, len(seq) - 1, target)
        return np.stack(
            [np.interp(idx_new, idx_old, seq[:, c]) for c in range(seq.shape[1])],
            axis=1,
        ).astype(np.float32)

    def save(self, frames: list, sign_id: str) -> Path:
        seq = np.stack(frames)
        seq = self.normalize(seq)
        seq = self.resample(seq)

        out = OUT_DIR / sign_id
        out.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out / f"{sign_id}__{self.signer_id}__{stamp}.npy"
        np.save(path, seq)

        meta = {
            "sign_id": sign_id,
            "signer_id": self.signer_id,
            "recorded_at": stamp,
            "seq_len": SEQ_LEN,
            "feature_dim": int(seq.shape[1]),
            "normalized": True,
        }
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        return path


def count_takes(sign_id: str, signer_id: str) -> int:
    d = OUT_DIR / sign_id
    if not d.exists():
        return 0
    return len(list(d.glob(f"{sign_id}__{signer_id}__*.npy")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signer", required=True, help="Signer ID, e.g. S01")
    ap.add_argument("--sign", required=True, help="Sign ID, e.g. NSL_0001")
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open camera {args.camera}")

    capture = LandmarkCapture(args.signer)
    recording, buffer, last_saved = False, [], None
    sign_id = args.sign

    print(f"Signer {args.signer} | Sign {sign_id}")
    print("SPACE = record/stop, d = delete last, q = quit\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = capture.holistic.process(rgb)

        # Overlays
        h = mp.solutions.holistic
        capture.drawer.draw_landmarks(frame, results.pose_landmarks, h.POSE_CONNECTIONS)
        capture.drawer.draw_landmarks(frame, results.left_hand_landmarks, h.HAND_CONNECTIONS)
        capture.drawer.draw_landmarks(frame, results.right_hand_landmarks, h.HAND_CONNECTIONS)

        if recording:
            buffer.append(capture.extract(results))
            cv2.circle(frame, (30, 30), 12, (0, 0, 255), -1)
            cv2.putText(frame, f"REC {len(buffer)}", (50, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        n = count_takes(sign_id, args.signer)
        cv2.putText(frame, f"{sign_id} | {args.signer} | takes: {n}",
                    (10, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Warn on missing hands — a take with no hands is a wasted take
        if results.left_hand_landmarks is None and results.right_hand_landmarks is None:
            cv2.putText(frame, "NO HANDS DETECTED", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        cv2.imshow("SignBridge Capture", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(" "):
            if recording:
                recording = False
                if len(buffer) >= 10:
                    last_saved = capture.save(buffer, sign_id)
                    print(f"saved {last_saved.name}  ({len(buffer)} frames)")
                else:
                    print("too short, discarded")
                buffer = []
            else:
                recording, buffer = True, []

        elif key == ord("d") and last_saved:
            last_saved.unlink(missing_ok=True)
            last_saved.with_suffix(".json").unlink(missing_ok=True)
            print(f"deleted {last_saved.name}")
            last_saved = None

        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    capture.holistic.close()


if __name__ == "__main__":
    main()
