"use client";

// Phase 2 signing avatar — a full articulated humanoid: head, torso, hips, legs, and two
// arms driven by 2-bone IK to reach each sign's hand position, with five-fingered hands
// that curl per handshape. Plays an animation plan (from /produce) with co-articulation
// blending and an ARKit-derived facial track.
//
// This is still a procedural stand-in for an authored, skinned character. The `clip_ref`
// seam (and web/public/avatar/ — see docs/avatar-authoring.md) is where a rigged Blender /
// Ready Player Me glTF with ARKit blendshapes takes over.

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { ProducePlan } from "@/lib/api";
import { sample, type Vec3 } from "@/lib/playback";

const CHEST_Y = 1.15; // pose-space origin (mid-chest) in world coords
const SHOULDER_R: Vec3 = [0.19, 1.4, 0.02];
const SHOULDER_L: Vec3 = [-0.19, 1.4, 0.02];
const UPPER_ARM = 0.3;
const FOREARM = 0.3;

const SKIN = "#d7a17f";
const SHIRT = "#4f6bd0";
const PANTS = "#33415c";
const HAIR = "#2b2320";

type Holder = { current: THREE.Group | null };
const makeHandJoints = (): Holder[][] =>
  Array.from({ length: 5 }, () => Array.from({ length: 3 }, () => ({ current: null } as Holder)));

function toWorld(p: Vec3): THREE.Vector3 {
  return new THREE.Vector3(p[0], CHEST_Y + p[1], p[2]);
}

// Per-finger curl [thumb, index, middle, ring, pinky] from the handshape label.
function fingerCurls(handshape: string, curl: number): number[] {
  const h = (handshape || "").toLowerCase();
  const all = (v: number) => [v, v, v, v, v];
  if (h.includes("fist") || h.includes("_a") || h.includes("_s")) return all(0.95);
  if (h.includes("flat") || h.includes("_b") || h.includes("_5") || h.includes("open"))
    return [0.15, 0.05, 0.05, 0.05, 0.05];
  if (h.includes("_v") || h.includes("hand_2")) return [0.85, 0.05, 0.05, 0.9, 0.9];
  if (h.includes("index") || h.includes("_d") || h.includes("_u")) return [0.85, 0.05, 0.9, 0.9, 0.9];
  if (h.includes("thumb")) return [0.05, 0.9, 0.9, 0.9, 0.9];
  if (h.includes("claw") || h.includes("curved")) return all(0.5);
  if (h.includes("pinch")) return [0.6, 0.55, 0.4, 0.3, 0.3];
  return all(Math.min(Math.max(curl, 0.1), 0.9));
}

// 2-bone IK: elbow position so a chain (l1,l2) from `root` reaches `target`, bending
// toward `pole`.
function solveIK(root: THREE.Vector3, target: THREE.Vector3, l1: number, l2: number, pole: THREE.Vector3) {
  const toT = target.clone().sub(root);
  let d = toT.length();
  const maxd = (l1 + l2) * 0.999;
  if (d > maxd) {
    toT.setLength(maxd);
    d = maxd;
  }
  if (d < 1e-4) return root.clone();
  const dir = toT.clone().normalize();
  const cosA = Math.min(Math.max((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1), 1);
  const a = Math.acos(cosA);
  const normal = new THREE.Vector3().crossVectors(dir, pole);
  if (normal.lengthSq() < 1e-6) normal.set(0, 0, 1);
  else normal.normalize();
  const upperDir = dir.clone().applyAxisAngle(normal, a);
  return root.clone().add(upperDir.multiplyScalar(l1));
}

// Orient + stretch a unit-height (1.0) capsule to connect two points.
function connectBone(mesh: THREE.Object3D, from: THREE.Vector3, to: THREE.Vector3) {
  const dir = new THREE.Vector3().subVectors(to, from);
  const len = dir.length();
  mesh.position.copy(from).addScaledVector(dir, 0.5);
  mesh.scale.set(1, Math.max(len, 0.001), 1);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
}

function Finger({
  joints,
  position,
  rotation = [0, 0, 0],
  length,
  radius,
  mat,
}: {
  joints: Holder[];
  position: [number, number, number];
  rotation?: [number, number, number];
  length: number;
  radius: number;
  mat: THREE.Material;
}) {
  const seg = length / 3;
  return (
    <group position={position} rotation={rotation}>
      <group ref={(g) => { joints[0].current = g; }}>
        <mesh position={[0, seg / 2, 0]} material={mat}>
          <capsuleGeometry args={[radius, seg, 3, 6]} />
        </mesh>
        <group position={[0, seg, 0]} ref={(g) => { joints[1].current = g; }}>
          <mesh position={[0, seg / 2, 0]} material={mat}>
            <capsuleGeometry args={[radius * 0.9, seg, 3, 6]} />
          </mesh>
          <group position={[0, seg, 0]} ref={(g) => { joints[2].current = g; }}>
            <mesh position={[0, seg / 2, 0]} material={mat}>
              <capsuleGeometry args={[radius * 0.8, seg, 3, 6]} />
            </mesh>
          </group>
        </group>
      </group>
    </group>
  );
}

function Hand({ groupRef, joints, mat }: { groupRef: React.RefObject<THREE.Group | null>; joints: Holder[][]; mat: THREE.Material }) {
  return (
    <group ref={groupRef}>
      {/* palm */}
      <mesh material={mat}>
        <boxGeometry args={[0.085, 0.1, 0.035]} />
      </mesh>
      {/* four fingers across the top of the palm */}
      <Finger joints={joints[1]} position={[-0.032, 0.05, 0]} length={0.11} radius={0.011} mat={mat} />
      <Finger joints={joints[2]} position={[-0.011, 0.05, 0]} length={0.125} radius={0.012} mat={mat} />
      <Finger joints={joints[3]} position={[0.011, 0.05, 0]} length={0.115} radius={0.011} mat={mat} />
      <Finger joints={joints[4]} position={[0.032, 0.048, 0]} length={0.095} radius={0.01} mat={mat} />
      {/* thumb, off the side */}
      <Finger joints={joints[0]} position={[-0.045, -0.015, 0.015]} rotation={[0.3, 0, 0.9]} length={0.08} radius={0.013} mat={mat} />
    </group>
  );
}

function applyFingerCurl(joints: Holder[][], shape: string, curl: number) {
  const c = fingerCurls(shape, curl);
  for (let f = 0; f < 5; f++) {
    const bend = c[f];
    if (joints[f][0].current) joints[f][0].current!.rotation.x = -bend * 0.5;
    if (joints[f][1].current) joints[f][1].current!.rotation.x = -bend * 1.1;
    if (joints[f][2].current) joints[f][2].current!.rotation.x = -bend * 0.8;
  }
}

function Rig({ plan, speed = 1 }: { plan: ProducePlan | null; speed?: number }) {
  const rHand = useRef<THREE.Group>(null);
  const lHand = useRef<THREE.Group>(null);
  const rUpper = useRef<THREE.Mesh>(null);
  const rFore = useRef<THREE.Mesh>(null);
  const lUpper = useRef<THREE.Mesh>(null);
  const lFore = useRef<THREE.Mesh>(null);
  const head = useRef<THREE.Group>(null);
  const browL = useRef<THREE.Mesh>(null);
  const browR = useRef<THREE.Mesh>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const start = useRef<number>(performance.now());

  const rFingers = useMemo(makeHandJoints, []);
  const lFingers = useMemo(makeHandJoints, []);
  const skinMat = useMemo(() => new THREE.MeshStandardMaterial({ color: SKIN }), []);
  const boneGeom = useMemo(() => new THREE.CapsuleGeometry(0.045, 1, 4, 8), []);

  useFrame(() => {
    const neutralR: Vec3 = [0.28, -0.28, 0.28];
    const neutralL: Vec3 = [-0.28, -0.28, 0.28];
    const f = plan ? sample(plan, (performance.now() - start.current) * speed) : null;

    const rTarget = toWorld(f?.right ?? neutralR);
    const lTarget = toWorld(f?.left ?? neutralL);
    const shoulderR = new THREE.Vector3(...SHOULDER_R);
    const shoulderL = new THREE.Vector3(...SHOULDER_L);

    // Right arm IK (elbow bends down-and-out).
    const elbowR = solveIK(shoulderR, rTarget, UPPER_ARM, FOREARM, new THREE.Vector3(0.6, -1, -0.3));
    if (rUpper.current) connectBone(rUpper.current, shoulderR, elbowR);
    if (rFore.current) connectBone(rFore.current, elbowR, rTarget);
    if (rHand.current) {
      rHand.current.position.copy(rTarget);
      rHand.current.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        rTarget.clone().sub(elbowR).normalize(),
      );
    }
    applyFingerCurl(rFingers, f?.rightShape ?? "", f?.rightCurl ?? 0.2);

    // Left arm.
    const showLeft = !plan || !!f?.left;
    const elbowL = solveIK(shoulderL, lTarget, UPPER_ARM, FOREARM, new THREE.Vector3(-0.6, -1, -0.3));
    if (lUpper.current) { connectBone(lUpper.current, shoulderL, elbowL); lUpper.current.visible = showLeft; }
    if (lFore.current) { connectBone(lFore.current, elbowL, lTarget); lFore.current.visible = showLeft; }
    if (lHand.current) {
      lHand.current.visible = showLeft;
      lHand.current.position.copy(lTarget);
      lHand.current.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        lTarget.clone().sub(elbowL).normalize(),
      );
    }
    applyFingerCurl(lFingers, f?.leftShape ?? "", f?.leftCurl ?? 0.2);

    // Face.
    const brow = f?.brow ?? { up: 0, down: 0 };
    const browY = 0.12 + brow.up * 0.03;
    if (browL.current) { browL.current.position.y = browY; browL.current.rotation.z = -brow.down * 0.5; }
    if (browR.current) { browR.current.position.y = browY; browR.current.rotation.z = brow.down * 0.5; }
    if (mouth.current) {
      const open = f?.jawOpen ?? 0;
      const smile = f?.smile ?? 0;
      const pucker = f?.pucker ?? 0;
      mouth.current.scale.set(1 + smile * 0.8 - pucker * 0.5, 0.4 + open * 2.4 + pucker * 0.4, 1);
    }
    if (head.current) {
      const hs = f?.headStatic ?? [0, 0, 0];
      let gx = 0, gy = 0;
      if (f?.headGesture === "nod") gx = Math.sin(performance.now() / 180) * 0.14;
      if (f?.headGesture === "shake") gy = Math.sin(performance.now() / 160) * 0.2;
      head.current.rotation.set(hs[0] + gx, hs[1] + gy, hs[2]);
    }
  });

  return (
    <group>
      {/* head + face */}
      <group ref={head} position={[0, 1.62, 0]}>
        <mesh material={skinMat}>
          <sphereGeometry args={[0.135, 32, 32]} />
        </mesh>
        {/* hair cap */}
        <mesh position={[0, 0.03, -0.01]}>
          <sphereGeometry args={[0.142, 24, 24, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
          <meshStandardMaterial color={HAIR} />
        </mesh>
        <mesh ref={browL} position={[-0.05, 0.12, 0.12]}>
          <boxGeometry args={[0.05, 0.012, 0.02]} />
          <meshStandardMaterial color={HAIR} />
        </mesh>
        <mesh ref={browR} position={[0.05, 0.12, 0.12]}>
          <boxGeometry args={[0.05, 0.012, 0.02]} />
          <meshStandardMaterial color={HAIR} />
        </mesh>
        {/* eyes */}
        <mesh position={[-0.05, 0.04, 0.12]}><sphereGeometry args={[0.02, 12, 12]} /><meshStandardMaterial color="#222" /></mesh>
        <mesh position={[0.05, 0.04, 0.12]}><sphereGeometry args={[0.02, 12, 12]} /><meshStandardMaterial color="#222" /></mesh>
        <mesh ref={mouth} position={[0, -0.06, 0.12]}>
          <boxGeometry args={[0.06, 0.02, 0.02]} />
          <meshStandardMaterial color="#8a4b4b" />
        </mesh>
      </group>

      {/* neck + torso + hips */}
      <mesh position={[0, 1.48, 0]} material={skinMat}><cylinderGeometry args={[0.05, 0.06, 0.1, 12]} /></mesh>
      <mesh position={[0, 1.2, 0]}>
        <capsuleGeometry args={[0.19, 0.42, 8, 16]} />
        <meshStandardMaterial color={SHIRT} />
      </mesh>
      <mesh position={[0, 0.92, 0]}>
        <capsuleGeometry args={[0.17, 0.12, 6, 12]} />
        <meshStandardMaterial color={PANTS} />
      </mesh>

      {/* legs */}
      {[-0.1, 0.1].map((x) => (
        <group key={x}>
          <mesh position={[x, 0.62, 0]}>
            <capsuleGeometry args={[0.075, 0.42, 6, 12]} />
            <meshStandardMaterial color={PANTS} />
          </mesh>
          <mesh position={[x, 0.2, 0]}>
            <capsuleGeometry args={[0.06, 0.36, 6, 12]} />
            <meshStandardMaterial color={PANTS} />
          </mesh>
          <mesh position={[x, 0.02, 0.05]}>
            <boxGeometry args={[0.09, 0.05, 0.2]} />
            <meshStandardMaterial color="#20242c" />
          </mesh>
        </group>
      ))}

      {/* arms (IK-driven each frame) */}
      <mesh ref={rUpper} geometry={boneGeom} material={skinMat} />
      <mesh ref={rFore} geometry={boneGeom} material={skinMat} />
      <mesh ref={lUpper} geometry={boneGeom} material={skinMat} />
      <mesh ref={lFore} geometry={boneGeom} material={skinMat} />
      <Hand groupRef={rHand} joints={rFingers} mat={skinMat} />
      <Hand groupRef={lHand} joints={lFingers} mat={skinMat} />
    </group>
  );
}

export default function SigningAvatar({ plan, speed = 1 }: { plan: ProducePlan | null; speed?: number }) {
  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-xl bg-gradient-to-b from-slate-800/40 to-black/50 sm:aspect-video">
      <Canvas camera={{ position: [0, 1.25, 2.3], fov: 42 }} shadows>
        <ambientLight intensity={0.7} />
        <directionalLight position={[2, 4, 3]} intensity={1.3} />
        <directionalLight position={[-2, 2, 1]} intensity={0.4} />
        <Rig plan={plan} speed={speed} />
        <OrbitControls enablePan={false} target={[0, 1.15, 0]} minDistance={1.4} maxDistance={5} />
      </Canvas>
    </div>
  );
}
