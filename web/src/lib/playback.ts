// Pure playback math for the signing avatar: given an animation plan and a time, compute
// where each hand is and how the face is posed, with co-articulation blending between signs.

import type { AnimationStep, ProducePlan } from "./api";

export type Vec3 = [number, number, number];

const NEUTRAL_R: Vec3 = [0.25, -0.15, 0.3];
const NEUTRAL_L: Vec3 = [-0.25, -0.15, 0.3];

function lerp3(a: Vec3, b: Vec3, t: number): Vec3 {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

/** Offset added to a hand's base location over the sign's local phase p in [0,1]. */
export function movementOffset(
  kind: string,
  amp: number,
  repeats: number,
  p: number,
  side: 1 | -1,
): Vec3 {
  const tau = Math.PI * 2;
  switch (kind) {
    case "static":
      return [0, 0, 0];
    case "tap":
      return [0, -amp * Math.abs(Math.sin(Math.PI * repeats * p)), 0];
    case "arc":
      return [0, amp * Math.sin(Math.PI * p), amp * 0.5 * Math.sin(Math.PI * p)];
    case "circle":
      return [amp * Math.cos(tau * repeats * p), amp * Math.sin(tau * repeats * p), 0];
    case "oscillate_x":
      return [amp * Math.sin(tau * repeats * p) * side, 0, 0];
    case "down":
      return [0, -amp * p, 0];
    case "up":
      return [0, amp * p, 0];
    case "wave":
      return [amp * Math.sin(tau * repeats * p) * side, amp * 0.3, 0];
    case "tremble":
      return [amp * Math.sin(tau * repeats * 3 * p) * side, amp * 0.5 * Math.cos(tau * repeats * 3 * p), 0];
    case "scale":
      return [amp * Math.sin(Math.PI * p) * side, 0, 0];
    case "twist":
      return [0, 0, amp * Math.sin(Math.PI * p)];
    case "meet":
      return [-amp * Math.sin(Math.PI * p) * side, 0, 0];
    default:
      return [0, amp * Math.sin(Math.PI * p), 0];
  }
}

export interface PoseFrame {
  right: Vec3;
  rightCurl: number;
  left: Vec3 | null;
  leftCurl: number;
  brow: { up: number; down: number };
  jawOpen: number;
  smile: number;
  pucker: number;
  headStatic: Vec3;
  headGesture: "nod" | "shake" | null;
  gesturePhase: number;
  signId: string;
  gloss: string;
}

function activeStep(plan: ProducePlan, t: number): AnimationStep {
  // The latest step that has started by time t (steps overlap during crossfade).
  let cur = plan.steps[0];
  for (const s of plan.steps) if (s.start_ms <= t) cur = s;
  return cur;
}

function facialTargets(step: AnimationStep) {
  const b = step.facial.blendshapes || {};
  return {
    brow: {
      up: b["browInnerUp"] ?? 0,
      down: Math.max(b["browDownLeft"] ?? 0, b["browDownRight"] ?? 0),
    },
    jawOpen: b["jawOpen"] ?? 0,
    smile: Math.max(b["mouthSmileLeft"] ?? 0, b["mouthSmileRight"] ?? 0),
    pucker: b["mouthPucker"] ?? 0,
  };
}

function handBase(step: AnimationStep, which: "right" | "left"): Vec3 | null {
  if (!step.pose) return which === "right" ? NEUTRAL_R : NEUTRAL_L;
  if (which === "right") return step.pose.right_hand.location as Vec3;
  return (step.pose.left_hand?.location as Vec3) ?? null;
}

/** Sample the plan at time t (ms). Loops over plan.total_ms. */
export function sample(plan: ProducePlan, tMs: number): PoseFrame {
  const t = plan.total_ms > 0 ? tMs % plan.total_ms : 0;
  const step = activeStep(plan, t);
  const idx = plan.steps.indexOf(step);
  const prev = idx > 0 ? plan.steps[idx - 1] : null;

  const p = Math.min(Math.max((t - step.start_ms) / Math.max(step.duration_ms, 1), 0), 1);
  const mv = step.pose?.movement ?? { kind: "static", amplitude: 0, repeats: 1 };

  // Base positions with movement offset.
  let right = handBase(step, "right") ?? NEUTRAL_R;
  right = add(right, movementOffset(mv.kind, mv.amplitude, mv.repeats, p, 1));
  let left = handBase(step, "left");
  if (left) left = add(left, movementOffset(mv.kind, mv.amplitude, mv.repeats, p, -1));

  const fac = facialTargets(step);

  // Co-articulation crossfade at the start of a step: blend from the previous sign's pose.
  if (prev && step.crossfade_ms > 0) {
    const cf = Math.min((t - step.start_ms) / step.crossfade_ms, 1);
    if (cf < 1) {
      const prevR = add(handBase(prev, "right") ?? NEUTRAL_R, [0, 0, 0]);
      right = lerp3(prevR, right, cf);
      const prevL = handBase(prev, "left");
      if (left && prevL) left = lerp3(prevL, left, cf);
    }
  }

  return {
    right,
    rightCurl: step.pose?.right_hand.curl ?? 0.2,
    left,
    leftCurl: step.pose?.left_hand?.curl ?? 0.2,
    brow: fac.brow,
    jawOpen: fac.jawOpen,
    smile: fac.smile,
    pucker: fac.pucker,
    headStatic: step.facial.head_rotation as Vec3,
    headGesture: step.facial.head_gesture,
    gesturePhase: p,
    signId: step.sign_id,
    gloss: step.gloss,
  };
}

function add(a: Vec3, b: Vec3): Vec3 {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}
