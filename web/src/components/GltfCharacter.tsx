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

interface Rig {
  bones: Record<string, THREE.Bone>;
  morphMeshes: THREE.SkinnedMesh[];
  chest?: THREE.Object3D;
}

function collectRig(root: THREE.Object3D): Rig {
  const bones: Record<string, THREE.Bone> = {};
  const morphMeshes: THREE.SkinnedMesh[] = [];
  root.traverse((o) => {
    if ((o as THREE.Bone).isBone) bones[o.name] = o as THREE.Bone;
    const sk = o as THREE.SkinnedMesh;
    if (sk.isSkinnedMesh && sk.morphTargetDictionary) morphMeshes.push(sk);
  });
  return { bones, morphMeshes, chest: bones["Spine2"] ?? bones["Spine1"] ?? bones["Spine"] };
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

  useEffect(() => {
    model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true;
        m.frustumCulled = false;
      }
    });
  }, [model]);

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

    // --- fingers (curl) ---
    const curlHand = (side: "Left" | "Right", curl: number) => {
      for (const fname of FINGER_BONES) {
        for (let j = 1; j <= 3; j++) {
          const b = bones[`${side}Hand${fname}${j}`];
          if (b) b.rotation.z = (side === "Left" ? 1 : -1) * curl * 1.1;
        }
      }
    };
    if (f) {
      curlHand("Right", f.rightCurl);
      if (f.left) curlHand("Left", f.leftCurl);
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
