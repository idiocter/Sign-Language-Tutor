#!/usr/bin/env bash
# Download the MediaPipe Task models the in-browser recognizer needs.
# Verify URLs against Guide/files/DOWNLOADS.md — MediaPipe bumps version paths.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/web/public/models/mediapipe"
mkdir -p "$DEST"
cd "$DEST"

base="https://storage.googleapis.com/mediapipe-models"
echo "Downloading MediaPipe .task models into $DEST"
curl -fL -o hand_landmarker.task "$base/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
curl -fL -o pose_landmarker.task "$base/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"
curl -fL -o face_landmarker.task "$base/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
echo "Done:"
ls -lh "$DEST"/*.task
