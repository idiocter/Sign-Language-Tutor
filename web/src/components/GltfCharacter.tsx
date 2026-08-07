"use client";

// Loads a real rigged glTF character (e.g. a Ready Player Me avatar of you) and drives it
// with the sign animation: CCD inverse kinematics moves each arm toward the sign's hand
// target, finger bones curl per handshape, and the face is driven by ARKit blendshapes
// (which RPM avatars ship with). Falls back to nothing (parent shows the procedural avatar)
// if the model can't load.
//
// Standard Mixamo/Ready-Player-Me bone names are assumed. The IK is rest-pose-agnostic
// (it aims bones by their current direction), so it works across rigs — but exact reach
// and finger axes may need tuning once visible.

import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { ProducePlan } from "@/lib/api";
import { sample } from "@/lib/playback";
import { CURL_JOINT_MAX, SPREAD_FAN, SPREAD_MAX, type HandShape, type Five } from "@/lib/handshapes";

interface Rig {
  bones: Record<string, THREE.Bone>;
  morphMeshes: THREE.SkinnedMesh[];
  chest?: THREE.Object3D;
}

// Different exporters name the same bone differently: Mixamo (and three.js's Xbot/Soldier)
// prefix every bone with "mixamorig:" (e.g. "mixamorig:RightArm"), while Ready Player Me
// ships them bare ("RightArm"). Normalize to the bare name so the same IK code drives both.
function normalizeBoneName(n: string): string {
  return n.replace(/^mixamorig[:_ ]?/i, "");
}

function collectRig(root: THREE.Object3D): Rig {
  const bones: Record<string, THREE.Bone> = {};
  const morphMeshes: THREE.SkinnedMesh[] = [];
  root.traverse((o) => {
    if ((o as THREE.Bone).isBone) {
      const bone = o as THREE.Bone;
      bones[o.name] = bone;
      const norm = normalizeBoneName(o.name);
      if (!(norm in bones)) bones[norm] = bone; // don't clobber an already-bare name
    }
    const sk = o as THREE.SkinnedMesh;
    if (sk.isSkinnedMesh && sk.morphTargetDictionary) morphMeshes.push(sk);
  });
  return { bones, morphMeshes, chest: bones["Spine2"] ?? bones["Spine1"] ?? bones["Spine"] };
}

// Scale + recenter any dropped-in model to a consistent human height with feet on the
// ground, so the framing/lighting set up for the procedural rig also fits real avatars.
const TARGET_HEIGHT = 1.7;
function fitModel(model: THREE.Object3D) {
  model.position.set(0, 0, 0);
  model.scale.setScalar(1);
  model.updateWorldMatrix(true, true);
  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  const s = size.y > 1e-4 ? TARGET_HEIGHT / size.y : 1;
  model.scale.setScalar(s);
  // Feet at y=0, centered on x/z (box was measured at scale 1, so multiply by s).
  model.position.set(-center.x * s, -box.min.y * s, -center.z * s);
}

// Chest-local sign coordinates -> world, using the model's chest bone as the origin.
function toModelWorld(chest: THREE.Object3D, p: [number, number, number]): THREE.Vector3 {
  const base = new THREE.Vector3();
  chest.getWorldPosition(base);
  return base.add(new THREE.Vector3(p[0], p[1] + 0.15, p[2]));
}

// Cyclic-Coordinate-Descent IK: rotate a chain so `effector` reaches `target`.
const _bp = new THREE.Vector3();
const _ep = new THREE.Vector3();
const _pq = new THREE.Quaternion();
const _bq = new THREE.Quaternion();
function ccd(chain: THREE.Bone[], effector: THREE.Bone, target: THREE.Vector3, iters = 5) {
  for (let it = 0; it < iters; it++) {
    for (const bone of chain) {
      if (!bone.parent) continue;
      bone.getWorldPosition(_bp);
      effector.getWorldPosition(_ep);
      const toEff = _ep.sub(_bp).normalize();
      const toTgt = target.clone().sub(_bp).normalize();
      const q = new THREE.Quaternion().setFromUnitVectors(toEff, toTgt);
      bone.getWorldQuaternion(_bq);
      bone.parent.getWorldQuaternion(_pq);
      const newLocal = _pq.invert().multiply(q.multiply(_bq));
      bone.quaternion.slerp(newLocal, 0.5); // damped for stability
      bone.updateWorldMatrix(false, true);
    }
  }
}

const FINGER_BONES = ["Thumb", "Index", "Middle", "Ring", "Pinky"];

// Pose one hand from a resolved handshape. Finger flexion is applied about the bone's local
// Z (the convention this rig already curled on), progressively over the three joints; finger
// spread is a small abduction about Y at the base knuckle; the thumb gets its own axes so it
// can sit across the palm or stand out. Everything is applied as an offset from each bone's
// captured rest orientation, so a resolved shape doesn't fight the model's natural rig.
const _delta = new THREE.Quaternion();
const _euler = new THREE.Euler();
function poseHand(
  bones: Record<string, THREE.Bone>,
  rest: Map<THREE.Bone, THREE.Quaternion>,
  side: "Left" | "Right",
  shape: HandShape,
) {
  const sgn = side === "Left" ? 1 : -1; // finger flexion curls the opposite way per hand
  const applyOffset = (b: THREE.Bone, x: number, y: number, z: number) => {
    const r = rest.get(b);
    if (!r) return;
    b.quaternion.copy(r).multiply(_delta.setFromEuler(_euler.set(x, y, z)));
  };

  // index..pinky
  for (let fi = 1; fi < 5; fi++) {
    const curl = shape.curl[fi];
    const spread = -sgn * SPREAD_FAN[fi] * shape.spread * SPREAD_MAX;
    for (let j = 1; j <= 3; j++) {
      const b = bones[`${side}Hand${FINGER_BONES[fi]}${j}`];
      if (!b) continue;
      applyOffset(b, 0, j === 1 ? spread : 0, sgn * curl * CURL_JOINT_MAX[j - 1]);
    }
  }

  // thumb: base knuckle opposes across the palm (thumbOut low) or abducts out (thumbOut high),
  // the two distal joints just flex.
  const across = 1 - shape.thumbOut;
  const t1 = bones[`${side}HandThumb1`];
  const t2 = bones[`${side}HandThumb2`];
  const t3 = bones[`${side}HandThumb3`];
  if (t1) applyOffset(t1, 0, sgn * across * 0.7, sgn * shape.curl[0] * 0.35);
  if (t2) applyOffset(t2, 0, 0, sgn * shape.curl[0] * 0.7);
  if (t3) applyOffset(t3, 0, 0, sgn * shape.curl[0] * 0.6);
}

// --- Palm / wrist orientation ------------------------------------------------------------
// Turn the hand so its palm faces the sign's palm-normal. The hand's own local axes (which
// way its fingers and palm point) are read from the rig's REST geometry — child-bone local
// positions — so this is correct for any humanoid rig with no hard-coded axis guesses. The
// palm-normal sign is auto-picked from the rest pose (a Mixamo T-pose has palms facing down).
interface HandAxes {
  point: THREE.Vector3; // toward the fingertips, hand-local
  normal: THREE.Vector3; // out of the palm, hand-local
  side: THREE.Vector3; // point × normal (right-handed)
}

function captureHandAxes(bones: Record<string, THREE.Bone>, side: "Left" | "Right"): HandAxes | null {
  const hand = bones[`${side}Hand`];
  const mid = bones[`${side}HandMiddle1`];
  const index = bones[`${side}HandIndex1`];
  const pinky = bones[`${side}HandPinky1`];
  if (!hand || !mid || !index || !pinky) return null;
  const point = mid.position.clone().normalize(); // child local pos = direction in hand frame
  const across = pinky.position.clone().sub(index.position); // knuckle line
  const normal = new THREE.Vector3().crossVectors(point, across).normalize();
  // Auto-orient the palm normal downward at rest (Mixamo T-pose palms face the floor).
  const worldNormal = normal.clone().applyQuaternion(hand.getWorldQuaternion(new THREE.Quaternion()));
  if (worldNormal.y > 0) normal.negate();
  const sideV = new THREE.Vector3().crossVectors(point, normal).normalize();
  normal.crossVectors(sideV, point).normalize(); // re-orthogonalize
  return { point, normal, side: sideV };
}

const _Tm = new THREE.Matrix4();
const _Sm = new THREE.Matrix4();
const _wPoint = new THREE.Vector3();
const _wNormal = new THREE.Vector3();
const _wSide = new THREE.Vector3();
const _handW = new THREE.Vector3();
const _foreW = new THREE.Vector3();
const _chestQ = new THREE.Quaternion();
const _parentQ = new THREE.Quaternion();
const _targetQ = new THREE.Quaternion();
function orientPalm(
  hand: THREE.Bone,
  fore: THREE.Bone,
  chest: THREE.Object3D,
  axes: HandAxes,
  palmLocal: [number, number, number],
  alpha: number,
) {
  if (!hand.parent) return;
  hand.getWorldPosition(_handW);
  fore.getWorldPosition(_foreW);
  _wPoint.copy(_handW).sub(_foreW).normalize(); // fingers continue past the wrist
  chest.getWorldQuaternion(_chestQ);
  _wNormal.set(palmLocal[0], palmLocal[1], palmLocal[2]).applyQuaternion(_chestQ);
  _wNormal.addScaledVector(_wPoint, -_wPoint.dot(_wNormal)).normalize(); // orthogonalize vs point
  _wSide.crossVectors(_wPoint, _wNormal).normalize();
  _Tm.makeBasis(_wPoint, _wNormal, _wSide);
  _Sm.makeBasis(axes.point, axes.normal, axes.side).invert();
  _Tm.multiply(_Sm); // world rotation mapping the hand's rest axes onto the target frame
  _targetQ.setFromRotationMatrix(_Tm);
  hand.parent.getWorldQuaternion(_parentQ);
  _targetQ.premultiply(_parentQ.invert()); // world → hand-local
  hand.quaternion.slerp(_targetQ, alpha);
  hand.updateWorldMatrix(false, true);
}

// Frame-rate-independent smoothing toward a ~90ms response, so hands glide between poses.
function smoothing(dtMs: number): number {
  return 1 - Math.exp(-Math.min(dtMs, 60) / 90);
}

interface CaptionOut {
  gloss: string;
  handshape: string;
  location: string;
  movement: string;
}

export default function GltfCharacter({
  url,
  plan,
  speed = 0.75,
  onCaption,
}: {
  url: string;
  plan: ProducePlan | null;
  speed?: number;
  onCaption?: (c: CaptionOut | null) => void;
}) {
  const { scene } = useGLTF(url);
  const model = useMemo(() => scene, [scene]);
  const rig = useMemo(() => collectRig(model), [model]);
  const animTime = useRef(0);
  const lastNow = useRef(performance.now());
  const lastGloss = useRef(" ");
  // Rest orientation of every finger bone, so handshape flexion is applied as an offset from
  // the model's natural rig rather than clobbering it.
  const fingerRest = useRef<Map<THREE.Bone, THREE.Quaternion>>(new Map());
  const handAxes = useRef<{ Left: HandAxes | null; Right: HandAxes | null }>({ Left: null, Right: null });
  // Smoothed state so hands glide between keyframes instead of snapping each frame.
  const rTarget = useRef<THREE.Vector3 | null>(null);
  const lTarget = useRef<THREE.Vector3 | null>(null);
  const rCurl = useRef<Five>([0.2, 0.2, 0.2, 0.2, 0.2]);
  const lCurl = useRef<Five>([0.2, 0.2, 0.2, 0.2, 0.2]);
  const basePos = useRef(new THREE.Vector3()); // fitted base position, for the idle bob

  useEffect(() => {
    model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true;
        m.frustumCulled = false;
      }
    });
    fitModel(model);
    model.updateWorldMatrix(true, true);
    basePos.current.copy(model.position);
    const rest = new Map<THREE.Bone, THREE.Quaternion>();
    for (const side of ["Left", "Right"] as const)
      for (const fname of FINGER_BONES)
        for (let j = 1; j <= 3; j++) {
          const b = rig.bones[`${side}Hand${fname}${j}`];
          if (b) rest.set(b, b.quaternion.clone());
        }
    fingerRest.current = rest;
    handAxes.current = { Left: captureHandAxes(rig.bones, "Left"), Right: captureHandAxes(rig.bones, "Right") };
  }, [model, rig]);

  useFrame(() => {
    const now = performance.now();
    const dtMs = now - lastNow.current;
    animTime.current += dtMs * speed;
    lastNow.current = now;
    const a = smoothing(dtMs);
    const f = plan ? sample(plan, animTime.current) : null;

    // Subtle idle so the figure breathes and sways instead of standing dead-still.
    model.position.y = basePos.current.y + Math.sin(now / 1400) * 0.004;
    model.rotation.y = Math.sin(now / 3600) * 0.015;

    const g = f?.gloss ?? "";
    if (onCaption && g !== lastGloss.current) {
      lastGloss.current = g;
      onCaption(
        f ? { gloss: f.gloss, handshape: f.handshapeLabel, location: f.locationLabel, movement: f.movementLabel } : null,
      );
    }

    const { bones, chest, morphMeshes } = rig;
    if (!chest) return;

    // --- arms (smoothed CCD IK) + palm orientation ---
    const driveArm = (
      side: "Left" | "Right",
      target: [number, number, number] | null,
      smooth: { current: THREE.Vector3 | null },
      palm: [number, number, number] | null,
    ) => {
      const upper = bones[`${side}Arm`];
      const fore = bones[`${side}ForeArm`];
      const hand = bones[`${side}Hand`];
      if (!upper || !fore || !hand || !target) return;
      const world = toModelWorld(chest, target);
      if (!smooth.current) smooth.current = world.clone();
      else smooth.current.lerp(world, a); // ease toward the target instead of snapping
      ccd([fore, upper], hand, smooth.current);
      const axes = handAxes.current[side];
      if (axes && palm) orientPalm(hand, fore, chest, axes, palm, a);
    };
    if (f) {
      driveArm("Right", f.right, rTarget, f.rightPalm);
      driveArm("Left", f.left, lTarget, f.leftPalm);
    }

    // --- fingers (smoothed per-finger articulation, from the backend's per-finger data) ---
    const driveFingers = (side: "Left" | "Right", shape: HandShape, cur: { current: Five }) => {
      for (let i = 0; i < 5; i++) cur.current[i] += (shape.curl[i] - cur.current[i]) * a;
      poseHand(bones, fingerRest.current, side, { curl: cur.current, spread: shape.spread, thumbOut: shape.thumbOut });
    };
    if (f) {
      driveFingers("Right", f.rightHand, rCurl);
      if (f.left && f.leftHand) driveFingers("Left", f.leftHand, lCurl);
    }

    // --- head gesture ---
    const head = bones["Head"];
    if (head && f) {
      let gx = f.headStatic[0];
      let gy = 0;
      if (f.headGesture === "nod") gx += Math.sin(now / 180) * 0.14;
      if (f.headGesture === "shake") gy += Math.sin(now / 160) * 0.2;
      head.rotation.x = gx;
      head.rotation.y = gy;
    }

    // --- face (ARKit blendshapes) ---
    const set = (mesh: THREE.SkinnedMesh, name: string, v: number) => {
      const i = mesh.morphTargetDictionary?.[name];
      if (i !== undefined && mesh.morphTargetInfluences) mesh.morphTargetInfluences[i] = v;
    };
    for (const mesh of morphMeshes) {
      const brow = f?.brow ?? { up: 0, down: 0 };
      set(mesh, "browInnerUp", brow.up);
      set(mesh, "browDownLeft", brow.down);
      set(mesh, "browDownRight", brow.down);
      set(mesh, "mouthSmileLeft", f?.smile ?? 0);
      set(mesh, "mouthSmileRight", f?.smile ?? 0);
      set(mesh, "jawOpen", f?.jawOpen ?? 0);
    }
  });

  // No position prop here: fitModel owns the model's transform (a prop would reset it on
  // every React re-render and undo the fit + idle bob).
  return <primitive object={model} />;
}
