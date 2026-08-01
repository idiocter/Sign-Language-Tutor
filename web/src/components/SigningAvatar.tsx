"use client";

// Phase 2 signing avatar. Plays an animation plan (from /produce) with co-articulation
// blending and an ARKit-derived facial track. Geometry is a legible placeholder — the
// `clip_ref` seam means an authored glTF clip overrides the procedural pose per sign.
//
// If a step carries an authored clip_ref, that's where a <ClipPlayer/> using drei's useGLTF
// would take over. No clips exist yet, so every sign is driven procedurally here.

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { ProducePlan } from "@/lib/api";
import { sample, type Vec3 } from "@/lib/playback";

const CHEST_Y = 0.9;
const SHOULDER_R: Vec3 = [0.32, 1.15, 0];
const SHOULDER_L: Vec3 = [-0.32, 1.15, 0];

function toWorld(p: Vec3): THREE.Vector3 {
  return new THREE.Vector3(p[0], CHEST_Y + p[1], p[2]);
}

// Orient + stretch a unit-height capsule (the "bone") to connect two points.
function connectBone(mesh: THREE.Object3D, from: THREE.Vector3, to: THREE.Vector3) {
  const dir = new THREE.Vector3().subVectors(to, from);
  const len = dir.length();
  mesh.position.copy(from).addScaledVector(dir, 0.5);
  mesh.scale.set(1, Math.max(len, 0.001), 1);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
}

function Hand({ groupRef }: { groupRef: React.RefObject<THREE.Group | null> }) {
  return (
    <group ref={groupRef}>
      <mesh>
        <boxGeometry args={[0.12, 0.14, 0.05]} />
        <meshStandardMaterial color="#c7b299" />
      </mesh>
      {/* fingers: a slab that bends with curl (rotated about its base) */}
      <group position={[0, 0.07, 0]}>
        <mesh position={[0, 0.06, 0]} name="fingers">
          <boxGeometry args={[0.11, 0.12, 0.04]} />
          <meshStandardMaterial color="#c7b299" />
        </mesh>
      </group>
    </group>
  );
}

function Rig({ plan, speed = 1 }: { plan: ProducePlan | null; speed?: number }) {
  const rightHand = useRef<THREE.Group>(null);
  const leftHand = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Mesh>(null);
  const leftArm = useRef<THREE.Mesh>(null);
  const head = useRef<THREE.Group>(null);
  const browL = useRef<THREE.Mesh>(null);
  const browR = useRef<THREE.Mesh>(null);
  const mouth = useRef<THREE.Mesh>(null);

  const start = useRef<number>(performance.now());

  useFrame(() => {
    const neutralR: Vec3 = [0.25, -0.15, 0.3];
    const neutralL: Vec3 = [-0.25, -0.15, 0.3];
    let f;
    if (plan) {
      const t = (performance.now() - start.current) * speed;
      f = sample(plan, t);
    } else {
      f = null;
    }
    const rPos = toWorld(f?.right ?? neutralR);
    const lPos = toWorld(f?.left ?? neutralL);

    if (rightHand.current) {
      rightHand.current.position.copy(rPos);
      const fingers = rightHand.current.getObjectByName("fingers");
      if (fingers) fingers.rotation.x = (f?.rightCurl ?? 0.2) * 1.4;
    }
    if (leftHand.current) {
      leftHand.current.position.copy(lPos);
      leftHand.current.visible = !plan || !!f?.left;
      const fingers = leftHand.current.getObjectByName("fingers");
      if (fingers) fingers.rotation.x = (f?.leftCurl ?? 0.2) * 1.4;
    }
    if (rightArm.current) connectBone(rightArm.current, new THREE.Vector3(...SHOULDER_R), rPos);
    if (leftArm.current) connectBone(leftArm.current, new THREE.Vector3(...SHOULDER_L), lPos);

    // --- Face ---
    const brow = f?.brow ?? { up: 0, down: 0 };
    const browY = 1.62 + brow.up * 0.05;
    const browTilt = brow.down * 0.5;
    if (browL.current) {
      browL.current.position.y = browY;
      browL.current.rotation.z = -browTilt;
    }
    if (browR.current) {
      browR.current.position.y = browY;
      browR.current.rotation.z = browTilt;
    }
    if (mouth.current) {
      const open = f?.jawOpen ?? 0;
      const smile = f?.smile ?? 0;
      const pucker = f?.pucker ?? 0;
      mouth.current.scale.set(1 + smile * 0.8 - pucker * 0.5, 0.4 + open * 2.2 + pucker * 0.4, 1);
    }

    // --- Head: static tilt + looped gesture ---
    if (head.current) {
      const hs = f?.headStatic ?? [0, 0, 0];
      let gx = 0;
      let gy = 0;
      if (f?.headGesture === "nod") gx = Math.sin(performance.now() / 180) * 0.15;
      if (f?.headGesture === "shake") gy = Math.sin(performance.now() / 160) * 0.2;
      head.current.rotation.set(hs[0] + gx, hs[1] + gy, hs[2]);
    }
  });

  const boneGeom = useMemo(() => new THREE.CapsuleGeometry(0.05, 1, 4, 8), []);
  const boneMat = useMemo(() => new THREE.MeshStandardMaterial({ color: "#8ea2c6" }), []);

  return (
    <group>
      {/* torso */}
      <mesh position={[0, 0.7, 0]}>
        <capsuleGeometry args={[0.28, 0.7, 8, 16]} />
        <meshStandardMaterial color="#5b8cff" />
      </mesh>
      {/* head */}
      <group ref={head} position={[0, 1.5, 0]}>
        <mesh>
          <sphereGeometry args={[0.28, 32, 32]} />
          <meshStandardMaterial color="#d8c3a5" />
        </mesh>
        <mesh ref={browL} position={[-0.1, 1.62 - 1.5, 0.25]}>
          <boxGeometry args={[0.09, 0.02, 0.02]} />
          <meshStandardMaterial color="#3a2f2a" />
        </mesh>
        <mesh ref={browR} position={[0.1, 1.62 - 1.5, 0.25]}>
          <boxGeometry args={[0.09, 0.02, 0.02]} />
          <meshStandardMaterial color="#3a2f2a" />
        </mesh>
        <mesh ref={mouth} position={[0, -0.1, 0.26]}>
          <boxGeometry args={[0.12, 0.04, 0.02]} />
          <meshStandardMaterial color="#7a3b3b" />
        </mesh>
      </group>
      {/* arms (connected each frame) */}
      <mesh ref={rightArm} geometry={boneGeom} material={boneMat} />
      <mesh ref={leftArm} geometry={boneGeom} material={boneMat} />
      <Hand groupRef={rightHand} />
      <Hand groupRef={leftHand} />
    </group>
  );
}

export default function SigningAvatar({
  plan,
  speed = 1,
}: {
  plan: ProducePlan | null;
  speed?: number;
}) {
  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-xl bg-black/40 sm:aspect-video">
      <Canvas camera={{ position: [0, 1.1, 2.6], fov: 45 }}>
        <ambientLight intensity={0.75} />
        <directionalLight position={[2, 4, 3]} intensity={1.2} />
        <Rig plan={plan} speed={speed} />
        <OrbitControls enablePan={false} target={[0, 1, 0]} minDistance={1.6} maxDistance={4.5} />
      </Canvas>
    </div>
  );
}
