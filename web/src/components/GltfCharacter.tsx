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
import { resolveHandShape, CURL_JOINT_MAX, SPREAD_FAN, SPREAD_MAX, type HandShape } from "@/lib/handshapes";

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

  useEffect(() => {
    model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true;
        m.frustumCulled = false;
      }
    });
    fitModel(model);
    const rest = new Map<THREE.Bone, THREE.Quaternion>();
    for (const side of ["Left", "Right"] as const)
      for (const fname of FINGER_BONES)
        for (let j = 1; j <= 3; j++) {
          const b = rig.bones[`${side}Hand${fname}${j}`];
          if (b) rest.set(b, b.quaternion.clone());
        }
    fingerRest.current = rest;
  }, [model, rig]);

  useFrame(() => {
    const now = performance.now();
    animTime.current += (now - lastNow.current) * speed;
    lastNow.current = now;
    const f = plan ? sample(plan, animTime.current) : null;

    const g = f?.gloss ?? "";
    if (onCaption && g !== lastGloss.current) {
      lastGloss.current = g;
      onCaption(
        f ? { gloss: f.gloss, handshape: f.handshapeLabel, location: f.locationLabel, movement: f.movementLabel } : null,
      );
    }

    const { bones, chest, morphMeshes } = rig;
    if (!chest) return;

    // --- arms (CCD IK toward the sign hand targets) ---
    const armIK = (side: "Left" | "Right", target: [number, number, number] | null) => {
      const upper = bones[`${side}Arm`];
      const fore = bones[`${side}ForeArm`];
      const hand = bones[`${side}Hand`];
      if (!upper || !fore || !hand || !target) return;
      ccd([fore, upper], hand, toModelWorld(chest, target));
    };
    if (f) {
      armIK("Right", f.right);
      armIK("Left", f.left);
    }

    // --- fingers (per-handshape articulation) ---
    // Resolve the handshape *label* (index_D, flat_5, fist_S, …) to per-finger flexion +
    // spread + thumb, instead of applying one uniform curl to every finger.
    if (f) {
      poseHand(bones, fingerRest.current, "Right", resolveHandShape(f.rightShape, f.rightCurl));
      if (f.left) poseHand(bones, fingerRest.current, "Left", resolveHandShape(f.leftShape, f.leftCurl));
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

  return <primitive object={model} position={[0, 0, 0]} />;
}
