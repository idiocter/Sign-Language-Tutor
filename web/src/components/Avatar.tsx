"use client";

// Signing avatar (Phase 2). The production version loads one authored glTF clip per sign
// and blends transitions with a ~150-250ms co-articulation window (TECH_STACK.md Layer 3).
//
// STUB: no .glb clips exist yet, so this renders a simple placeholder figure. The
// `signId` prop is the stable seam — swap the placeholder for a <ClipPlayer signId=.../>
// that resolves `clips/<sign>.glb` once the avatar clips are authored in Blender.

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh } from "three";

function PlaceholderFigure() {
  const head = useRef<Mesh>(null);
  useFrame((state) => {
    // Gentle idle motion so it reads as "waiting to sign", not frozen.
    if (head.current) {
      head.current.rotation.y = Math.sin(state.clock.elapsedTime) * 0.2;
    }
  });
  return (
    <group position={[0, -0.5, 0]}>
      {/* head */}
      <mesh ref={head} position={[0, 1.6, 0]}>
        <sphereGeometry args={[0.35, 32, 32]} />
        <meshStandardMaterial color="#8ea2c6" />
      </mesh>
      {/* torso */}
      <mesh position={[0, 0.7, 0]}>
        <capsuleGeometry args={[0.35, 0.8, 8, 16]} />
        <meshStandardMaterial color="#5b8cff" />
      </mesh>
      {/* arms */}
      {[-0.55, 0.55].map((x) => (
        <mesh key={x} position={[x, 0.8, 0]} rotation={[0, 0, x < 0 ? 0.3 : -0.3]}>
          <capsuleGeometry args={[0.12, 0.7, 8, 16]} />
          <meshStandardMaterial color="#8ea2c6" />
        </mesh>
      ))}
    </group>
  );
}

export default function Avatar({ signId }: { signId: string }) {
  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black/40">
      <Canvas camera={{ position: [0, 1, 3.2], fov: 45 }}>
        <ambientLight intensity={0.7} />
        <directionalLight position={[3, 5, 2]} intensity={1.2} />
        <PlaceholderFigure />
        <OrbitControls enablePan={false} minDistance={2} maxDistance={5} />
      </Canvas>
      <span className="pointer-events-none absolute bottom-2 left-3 rounded bg-black/50 px-2 py-1 text-xs text-white/70">
        {signId} · placeholder avatar
      </span>
    </div>
  );
}
