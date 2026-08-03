// Hand-authored keyframe animations for signs — the in-code equivalent of the authored
// glTF clips Phase 2 calls for. Each clip is a small choreography (hand trajectories,
// handshape changes, two-handed coordination, facial grammar) that reads like a person
// signing, instead of the generic phonology-derived motion.
//
// Coordinates are chest-local (origin mid-chest; +x right, +y up, +z forward toward the
// viewer), the same space posing.py / SigningAvatar use. Signs without a clip fall back to
// the procedural pose.
//
// HONEST NOTE: these are careful approximations, not deaf-advisor-validated NSL. They exist
// to make the avatar move like a signer for a demonstrable set; real signs still need
// authored mocap + community review. Handshape strings reuse the vocabulary vocabulary so
// the finger rig curls correctly (flat_B/flat_5 open, fist_A closed, index_D pointing…).

import type { Vec3 } from "./playback";

export interface HandKey {
  pos: Vec3;
  shape: string;
  curl: number;
}
export interface Keyframe {
  t: number; // 0..1 within the sign
  r: HandKey;
  l?: HandKey | null;
}
export interface SignClip {
  face?: { brow?: "raised" | "furrowed"; smile?: boolean; jawOpen?: number };
  head?: "nod" | "shake" | "forward";
  keys: Keyframe[];
}

const flat = (pos: Vec3, curl = 0.05, shape = "flat_B"): HandKey => ({ pos, shape, curl });
const fist = (pos: Vec3): HandKey => ({ pos, shape: "fist_A", curl: 0.95 });
const point = (pos: Vec3): HandKey => ({ pos, shape: "index_D", curl: 0.55 });
const five = (pos: Vec3): HandKey => ({ pos, shape: "flat_5", curl: 0.08 });

export const SIGN_CLIPS: Record<string, SignClip> = {
  // hello / namaste — two flat palms come together at the chest, slight bow
  NSL_0001: {
    face: { smile: true },
    head: "forward",
    keys: [
      { t: 0, r: flat([0.16, 0.02, 0.3]), l: flat([-0.16, 0.02, 0.3]) },
      { t: 0.45, r: flat([0.035, 0.12, 0.24]), l: flat([-0.035, 0.12, 0.24]) },
      { t: 1, r: flat([0.03, 0.1, 0.24]), l: flat([-0.03, 0.1, 0.24]) },
    ],
  },
  // thank you — flat hand from the chin moves outward and down toward the person
  NSL_0002: {
    face: { brow: "raised", smile: true },
    head: "nod",
    keys: [
      { t: 0, r: flat([0.02, 0.36, 0.2]) },
      { t: 0.5, r: flat([0.08, 0.22, 0.32]) },
      { t: 1, r: flat([0.14, 0.06, 0.4]) },
    ],
  },
  // sorry — fist circles over the chest
  NSL_0003: {
    face: { brow: "furrowed" },
    keys: [
      { t: 0, r: fist([0.02, 0.08, 0.22]) },
      { t: 0.33, r: fist([0.1, 0.14, 0.22]) },
      { t: 0.66, r: fist([0.02, 0.02, 0.22]) },
      { t: 1, r: fist([-0.04, 0.08, 0.22]) },
    ],
  },
  // yes — a fist "nods" up and down (like a knocking head)
  NSL_0005: {
    head: "nod",
    keys: [
      { t: 0, r: fist([0.22, 0.12, 0.32]) },
      { t: 0.35, r: { pos: [0.22, 0.02, 0.32], shape: "fist_A", curl: 0.95 } },
      { t: 0.7, r: fist([0.22, 0.12, 0.32]) },
      { t: 1, r: { pos: [0.22, 0.04, 0.32], shape: "fist_A", curl: 0.95 } },
    ],
  },
  // no — index+middle close onto the thumb, with a head shake
  NSL_0006: {
    face: { brow: "furrowed" },
    head: "shake",
    keys: [
      { t: 0, r: { pos: [0.2, 0.14, 0.32], shape: "index_V", curl: 0.15 } },
      { t: 0.5, r: { pos: [0.2, 0.14, 0.32], shape: "flat_O", curl: 0.7 } },
      { t: 1, r: { pos: [0.2, 0.14, 0.32], shape: "index_V", curl: 0.2 } },
    ],
  },
  // I / me — index points to own chest
  NSL_0011: {
    keys: [
      { t: 0, r: point([0.18, 0.0, 0.36]) },
      { t: 0.5, r: point([0.02, 0.06, 0.16]) },
      { t: 1, r: point([0.02, 0.06, 0.16]) },
    ],
  },
  // you — index points forward
  NSL_0012: {
    keys: [
      { t: 0, r: point([0.1, 0.06, 0.28]) },
      { t: 1, r: point([0.16, 0.06, 0.52]) },
    ],
  },
  // mother — open "5" hand, thumb taps the chin twice
  NSL_0015: {
    keys: [
      { t: 0, r: five([0.06, 0.3, 0.22]) },
      { t: 0.35, r: five([0.02, 0.34, 0.16]) },
      { t: 0.6, r: five([0.06, 0.3, 0.22]) },
      { t: 1, r: five([0.02, 0.34, 0.16]) },
    ],
  },
  // father — open "5" hand, thumb taps the forehead twice
  NSL_0016: {
    keys: [
      { t: 0, r: five([0.06, 0.5, 0.22]) },
      { t: 0.35, r: five([0.02, 0.54, 0.16]) },
      { t: 0.6, r: five([0.06, 0.5, 0.22]) },
      { t: 1, r: five([0.02, 0.54, 0.16]) },
    ],
  },
  // numbers — hold the handshape clearly in the signing space
  NSL_0021: { keys: [{ t: 0, r: { pos: [0.22, 0.16, 0.34], shape: "index_D", curl: 0.5 } }, { t: 1, r: { pos: [0.22, 0.2, 0.34], shape: "index_D", curl: 0.5 } }] },
  NSL_0022: { keys: [{ t: 0, r: { pos: [0.22, 0.16, 0.34], shape: "index_V", curl: 0.12 } }, { t: 1, r: { pos: [0.22, 0.2, 0.34], shape: "index_V", curl: 0.12 } }] },
  NSL_0023: { keys: [{ t: 0, r: { pos: [0.22, 0.16, 0.34], shape: "hand_3", curl: 0.12 } }, { t: 1, r: { pos: [0.22, 0.2, 0.34], shape: "hand_3", curl: 0.12 } }] },
  NSL_0025: { keys: [{ t: 0, r: five([0.22, 0.16, 0.34]) }, { t: 1, r: five([0.22, 0.2, 0.34]) }] },
  // happy — flat hands brush upward on the chest, twice
  NSL_0052: {
    face: { smile: true },
    keys: [
      { t: 0, r: flat([0.1, -0.02, 0.24]), l: flat([-0.1, -0.02, 0.24]) },
      { t: 0.4, r: flat([0.1, 0.14, 0.24]), l: flat([-0.1, 0.14, 0.24]) },
      { t: 0.6, r: flat([0.1, -0.02, 0.24]), l: flat([-0.1, -0.02, 0.24]) },
      { t: 1, r: flat([0.1, 0.14, 0.24]), l: flat([-0.1, 0.14, 0.24]) },
    ],
  },
};

function lerp3(a: Vec3, b: Vec3, t: number): Vec3 {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}
const smooth = (u: number) => u * u * (3 - 2 * u); // ease in/out

export interface ClipSample {
  right: Vec3;
  rightShape: string;
  rightCurl: number;
  left: Vec3 | null;
  leftShape: string;
  leftCurl: number;
  brow: { up: number; down: number };
  smile: number;
  jawOpen: number;
  headStatic: Vec3;
  headGesture: "nod" | "shake" | null;
}

/** Sample an authored clip at phase p in [0,1] with eased interpolation between keyframes. */
export function sampleClip(clip: SignClip, p: number): ClipSample {
  const keys = clip.keys;
  let k0 = keys[0];
  let k1 = keys[keys.length - 1];
  for (let i = 0; i < keys.length - 1; i++) {
    if (p >= keys[i].t && p <= keys[i + 1].t) {
      k0 = keys[i];
      k1 = keys[i + 1];
      break;
    }
  }
  const span = k1.t - k0.t;
  const u = span > 1e-6 ? smooth(Math.min(Math.max((p - k0.t) / span, 0), 1)) : 0;

  const right = lerp3(k0.r.pos, k1.r.pos, u);
  const rightCurl = k0.r.curl + (k1.r.curl - k0.r.curl) * u;
  const rightShape = u < 0.5 ? k0.r.shape : k1.r.shape;

  let left: Vec3 | null = null;
  let leftShape = "";
  let leftCurl = 0.2;
  if (k0.l && k1.l) {
    left = lerp3(k0.l.pos, k1.l.pos, u);
    leftCurl = k0.l.curl + (k1.l.curl - k0.l.curl) * u;
    leftShape = u < 0.5 ? k0.l.shape : k1.l.shape;
  } else if (k0.l ?? k1.l) {
    const h = (k0.l ?? k1.l)!;
    left = h.pos;
    leftShape = h.shape;
    leftCurl = h.curl;
  }

  const face = clip.face ?? {};
  const headMap: Record<string, { gesture: "nod" | "shake" | null; tilt: Vec3 }> = {
    nod: { gesture: "nod", tilt: [0, 0, 0] },
    shake: { gesture: "shake", tilt: [0, 0, 0] },
    forward: { gesture: null, tilt: [0.2, 0, 0] },
  };
  const head = clip.head ? headMap[clip.head] : { gesture: null, tilt: [0, 0, 0] as Vec3 };

  return {
    right,
    rightShape,
    rightCurl,
    left,
    leftShape,
    leftCurl,
    brow: { up: face.brow === "raised" ? 0.85 : 0, down: face.brow === "furrowed" ? 0.7 : 0 },
    smile: face.smile ? 0.6 : 0,
    jawOpen: face.jawOpen ?? 0,
    headStatic: head.tilt,
    headGesture: head.gesture,
  };
}
