// Landmark feature layout — must match ml/signbridge/config.py exactly.
// If you change the layout on the Python side, mirror it here or the ONNX model and the
// browser features will disagree.

export const SEQ_LEN = 60;
export const DIMS = 3;
export const POSE_PTS = 33;
export const HAND_PTS = 21;

// Same 68-index face subset the capture tool records (brows, eyes, mouth, jaw anchors).
export const FACE_SUBSET = [
  70, 63, 105, 66, 107, 336, 296, 334, 293, 300, 33, 133, 160, 159, 158, 144, 145, 153,
  362, 263, 387, 386, 385, 373, 374, 380, 61, 291, 39, 181, 0, 17, 269, 405, 84, 314, 78,
  308, 13, 14, 82, 87, 312, 317, 95, 88, 178, 87, 14, 317, 402, 318, 324, 1, 4, 5, 195,
  197, 6, 168, 8, 152, 148, 176, 149, 150, 136, 172, 58, 132,
];
export const FACE_PTS = FACE_SUBSET.length;

export const NUM_LANDMARKS = POSE_PTS + HAND_PTS + HAND_PTS + FACE_PTS;
export const FEATURE_DIM = NUM_LANDMARKS * DIMS;

const LEFT_SHOULDER = 11;
const RIGHT_SHOULDER = 12;

/**
 * Shoulder-normalize one frame: center on the shoulder midpoint, scale by shoulder width.
 * Mirrors preprocessing.normalize in Python. `frame` is a flat FEATURE_DIM vector.
 */
export function normalizeFrame(frame: Float32Array): Float32Array {
  const out = Float32Array.from(frame);
  const lx = out[LEFT_SHOULDER * DIMS];
  const ly = out[LEFT_SHOULDER * DIMS + 1];
  const rx = out[RIGHT_SHOULDER * DIMS];
  const ry = out[RIGHT_SHOULDER * DIMS + 1];
  const cx = (lx + rx) / 2;
  const cy = (ly + ry) / 2;
  let width = Math.hypot(lx - rx, ly - ry);
  if (width < 1e-6) width = 1;

  for (let i = 0; i < NUM_LANDMARKS; i++) {
    out[i * DIMS] = (out[i * DIMS] - cx) / width;
    out[i * DIMS + 1] = (out[i * DIMS + 1] - cy) / width;
    out[i * DIMS + 2] = out[i * DIMS + 2] / width;
  }
  return out;
}
