"""SignBridge — Phase 0 Capture Tool.

Records normalized landmark sequences for building the NSL dataset.

Why normalized landmarks and not video:
  - ~200x smaller on disk
  - Model learns signs, not camera distance or clothing
  - Runs on CPU, no GPU needed for collection

Why signer_id is mandatory:
  Your train/test split MUST be by signer, not by clip. Splitting by clip inflates
  accuracy 15-25 points and the model collapses on real users. You cannot do a signer
  split if you didn't record who signed what. (See preprocessing.split_by_signer.)

This is the guide's capture tool, wired to signbridge.config so the capture layout and the
model layout can never drift apart. Requires the ``full`` extra (mediapipe, opencv).

Usage:
    python -m signbridge.capture_tool --signer S01 --sign NSL_0001

Controls:
    SPACE   start / stop recording a take
    d       delete the last take
    q       quit
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from .config import FACE_SUBSET, HAND_PTS, POSE_PTS, RAW_DIR, SEQ_LEN
from .preprocessing import normalize, resample


class LandmarkCapture:
    def __init__(self, signer_id: str):
        import mediapipe as mp  # heavy import, deferred

        self.signer_id = signer_id
        self.mp = mp
        self.holistic = mp.solutions.holistic.Holistic(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1,
        )
        self.drawer = mp.solutions.drawing_utils

    def extract(self, results) -> np.ndarray:
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

    def save(self, frames: list, sign_id: str) -> Path:
        seq = np.stack(frames)
        seq = normalize(seq)
        seq = resample(seq, SEQ_LEN)

        out = RAW_DIR / sign_id
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
    d = RAW_DIR / sign_id
    if not d.exists():
        return 0
    return len(list(d.glob(f"{sign_id}__{signer_id}__*.npy")))


def main() -> None:
    import cv2  # heavy import, deferred

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
    h = capture.mp.solutions.holistic

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
