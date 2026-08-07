// Phonological handshape model — the accuracy core of the signing avatar.
//
// A sign's handshape is not a single "how closed is the hand" scalar: a pointing "D", a
// spread "V", an "F" ring, and a fist are all *equally* closed on average yet look nothing
// alike. Distinguishing them requires PER-FINGER flexion plus finger spread and a thumb
// configuration. This module maps each NSL/ASL handshape label (the same strings the pose
// plan and vocabulary use — "index_D", "flat_5", "fist_S", "hand_W", …) to that
// articulation, so distinct handshapes render as distinct hands.
//
// It is language-neutral (keyed by handshape identity, never by an English word) and is the
// single source of truth both the glTF avatar and the procedural rig apply, each mapping the
// normalized values onto its own bone axes.

// Finger order everywhere: [thumb, index, middle, ring, pinky].
export type Five = [number, number, number, number, number];

export interface HandShape {
  /** Per-finger flexion: 0 = straight/extended, 1 = fully folded into the palm. */
  curl: Five;
  /** How far the fingers fan apart: 0 = together, 1 = full splay. */
  spread: number;
  /** How far the thumb sits away from the palm: 0 = tucked/across, 1 = fully out. */
  thumbOut: number;
}

const H = (curl: Five, spread = 0, thumbOut = 0.35): HandShape => ({ curl, spread, thumbOut });

// Canonical inventory keyed by handshape identity — the letter/number after the family
// prefix ("index_D" -> "d", "flat_5" -> "5", "hand_W" -> "w", "thumb_up" -> "up").
const SHAPES: Record<string, HandShape> = {
  // --- closed / fist ---
  s: H([0.85, 1, 1, 1, 1], 0, 0.1), //  S: fist, thumb clamped across the front
  a: H([0.2, 1, 1, 1, 1], 0, 0.5), //   A: fist, thumb up alongside the index

  // --- flat / open ---
  b: H([0.7, 0.02, 0.02, 0.02, 0.02], 0, 0.0), // B: flat hand, fingers together, thumb across palm
  "5": H([0.1, 0.05, 0.05, 0.05, 0.05], 1, 1), //  5: open hand, fingers spread wide
  "4": H([0.95, 0.02, 0.02, 0.02, 0.02], 0.8, 0.0), // 4: four fingers spread, thumb tucked
  o: H([0.55, 0.6, 0.6, 0.6, 0.6], 0, 0.55), //   O / flat-O: fingertips curve to meet the thumb
  c: H([0.35, 0.4, 0.4, 0.42, 0.45], 0.25, 0.6), // C: cupped hand

  // --- pointing / index family ---
  d: H([0.55, 0.02, 0.85, 0.95, 0.95], 0, 0.2), // D: index up, others folded, thumb to middle
  "1": H([0.8, 0.02, 1, 1, 1], 0, 0.1), //         1: index up, others closed
  u: H([0.85, 0.02, 0.02, 1, 1], 0, 0.0), //       U: index + middle together, up
  v: H([0.85, 0.02, 0.02, 1, 1], 1, 0.0), //       V / 2: index + middle spread, up
  "2": H([0.85, 0.02, 0.02, 1, 1], 1, 0.0),
  hook: H([0.7, 0.55, 1, 1, 1], 0, 0.3), //        X / index_hook: bent (hooked) index
  x: H([0.7, 0.55, 1, 1, 1], 0, 0.3),

  // --- thumb-and-finger contacts ---
  f: H([0.5, 0.55, 0.02, 0.02, 0.02], 0.5, 0.4), // F / 9: thumb+index ring, three fingers up
  "9": H([0.5, 0.55, 0.02, 0.02, 0.02], 0.5, 0.4),
  g: H([0.2, 0.02, 1, 1, 1], 0, 0.75), //          G: thumb + index extended, parallel
  l: H([0.05, 0.02, 1, 1, 1], 0, 1), //            L: thumb + index at a right angle
  w: H([0.85, 0.02, 0.02, 0.02, 1], 0.7, 0.2), //  W: index+middle+ring up, pinky+thumb touch
  "6": H([0.85, 0.02, 0.02, 0.02, 1], 0.5, 0.2), // 6: same family as W
  "3": H([0.1, 0.02, 0.02, 1, 1], 0.5, 1), //      3: thumb + index + middle extended
  "7": H([0.6, 0.02, 0.02, 0.9, 0.02], 0.35, 0.4), // 7: ring folds to the thumb
  "8": H([0.5, 0.02, 0.85, 0.02, 0.02], 0.35, 0.4), // 8: middle folds to the thumb

  // --- thumb extended (10) ---
  up: H([0.05, 1, 1, 1, 1], 0, 0.85), //   thumb_up: fist with thumb extended
  down: H([0.05, 1, 1, 1, 1], 0, 0.85), // thumb_down: same shape, orientation differs
};

// Family prefixes are the fallback when the specific identity isn't tabulated.
const FAMILIES: Record<string, HandShape> = {
  fist: SHAPES.s,
  flat: SHAPES.b,
  index: SHAPES["1"],
  curved: SHAPES.c,
  claw: H([0.35, 0.45, 0.45, 0.45, 0.45], 1, 0.6), // clawed-5: spread and curved
  pinch: SHAPES.f,
  thumb: SHAPES.up,
  hand: SHAPES["5"],
};

const NEUTRAL: HandShape = H([0.25, 0.25, 0.25, 0.25, 0.25], 0.2, 0.4);
const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/**
 * Resolve a handshape label to its per-finger articulation.
 *
 * `scalarCurl` is the plan's single curl value, used only when the label is missing/unknown
 * so behaviour degrades to the old uniform curl instead of failing.
 */
export function resolveHandShape(label: string, scalarCurl = 0.3): HandShape {
  const l = (label || "").toLowerCase();
  if (!l) {
    const c = clamp01(scalarCurl);
    return { curl: [c, c, c, c, c], spread: 0.15, thumbOut: 0.4 };
  }
  const tokens = l.split(/[^a-z0-9]+/).filter(Boolean);

  // A specific handshape identity (letter/number) wins over the family prefix.
  let base: HandShape | undefined;
  for (const t of tokens) if (t in SHAPES) { base = SHAPES[t]; break; }
  if (!base) for (const t of tokens) if (t in FAMILIES) { base = FAMILIES[t]; break; }
  if (!base) base = NEUTRAL;

  let curl = [...base.curl] as Five;
  let { spread, thumbOut } = base;

  // "claw" rounds every extended finger into a curve (e.g. claw_5 vs flat_5).
  if (l.includes("claw")) {
    curl = curl.map((c) => Math.max(c, 0.45)) as Five;
    thumbOut = Math.max(thumbOut, 0.5);
  }
  return { curl, spread, thumbOut };
}

/**
 * Prefer the backend's per-finger articulation when the pose plan carries it (the backend is
 * the source of truth), otherwise resolve it here from the label. This keeps authored clips
 * and older plans — which only carry a label + scalar curl — working unchanged.
 */
export function handShapeFrom(
  pose: { fingers?: number[]; spread?: number; thumb_out?: number } | null | undefined,
  label: string,
  scalarCurl: number,
): HandShape {
  if (pose?.fingers && pose.fingers.length === 5) {
    return {
      curl: [...pose.fingers] as Five,
      spread: pose.spread ?? 0.15,
      thumbOut: pose.thumb_out ?? 0.4,
    };
  }
  return resolveHandShape(label, scalarCurl);
}

// --- Rig-application constants (each rig maps these onto its own bone axes) ---------------

/** Natural flexion (radians) at each of the three finger joints for a unit curl. */
export const CURL_JOINT_MAX: [number, number, number] = [1.3, 1.5, 1.1];

/** Lateral fan direction per finger [thumb, index, middle, ring, pinky] for `spread`. */
export const SPREAD_FAN: Five = [0, 0.55, 0.12, -0.38, -0.85];

/** Peak abduction (radians) applied at the base knuckle for `spread` = 1. */
export const SPREAD_MAX = 0.32;
