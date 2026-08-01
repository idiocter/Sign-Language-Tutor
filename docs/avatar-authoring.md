# Avatar clip authoring (Phase 2)

How to replace a sign's **procedural** placeholder motion with an **authored** glTF clip.

The pipeline plays clip-based animation, not neural synthesis (TECH_STACK.md Layer 3):
neural pose generation is still research-grade and produces unintelligible signing. You
author one clip per sign in Blender and the player blends transitions.

> **Non-negotiable (PROJECT_PLAN.md Phase 2):** the face is not optional. A clip with a
> static face fails the phase regardless of hand accuracy. Author the eyebrow, mouth, and
> head-motion tracks with ARKit blendshapes, and validate intelligibility with deaf
> advisors (target ≥4/5 on 20 signs).

## 0. The avatar today vs. a photoreal character

The web avatar (`web/src/components/SigningAvatar.tsx`) is now a **full articulated
humanoid** — head, torso, hips, legs, two arms driven by 2-bone IK, and five-fingered hands
that curl per handshape — but it is still procedural geometry (capsules), not a skinned
character. Two upgrade paths, both using the existing pose/facial data:

- **Realistic body:** drop a rigged glTF character (Ready Player Me / Mixamo) into
  `web/public/avatar/character.glb` and retarget: map the IK wrist targets to the model's
  hand bones and the finger curls to its finger bones. Same `sample()` data drives it.
- **Per-sign motion capture:** author one clip per sign (below) for exact, validated signing.

## 1. Character + rig (once)

1. Get a rigged humanoid with **ARKit 52 face blendshapes**:
   - [Ready Player Me](https://readyplayer.me) (has ARKit blendshapes), or
   - [Mixamo](https://mixamo.com) body rig + a face rig you add in Blender.
   - **Verify the face blendshapes exist before committing** — many free rigs are
     body-only, and retargeting a face later is painful (DOWNLOADS.md).
2. Confirm the 52 blendshape names match `ARKIT_BLENDSHAPES` in
   `ml/signbridge/facial.py`. Same 52-parameter space is used on the recognition side
   (MediaPipe face landmarker) — that's deliberate.

## 2. Author one clip per sign

For each sign, in Blender 4.x:

- Pose the hands for the sign's handshape / location / orientation and key the movement.
- Drive the **facial track** from the sign's `non_manual_markers` in the dictionary:
  eyebrows (raised/furrowed), mouth morpheme, head (nod/shake/tilt).
- Keep the clip ~0.9 s; the player crossfades ~200 ms between clips.

## 3. Export

- Export glTF Binary (`.glb`), Y-up, with shape keys / morph targets included.
- Name it by the **language-neutral sign id**, lowercased:
  `web/public/clips/nsl_0001.glb` (matches each sign's `clip_ref`).

## 4. It plugs itself in

No code change needed:

- `GET /clips/manifest` reports the sign as `authored` once the `.glb` is present.
- `/produce` sets `clip_ref` on that sign's step (instead of `null`).
- The frontend `SigningAvatar` loads the clip (drei `useGLTF`) and ignores the procedural
  pose for that sign. Signs without a clip keep signing procedurally.

`.glb` files are gitignored (large binaries) — store them in Cloudflare R2 for production
and sync into `web/public/clips/` for local dev.

## Checklist per sign

- [ ] hands match handshape / location / orientation / movement
- [ ] facial track present (brows + mouth + head) — not static
- [ ] exported as `nsl_dddd.glb`, Y-up, morph targets included
- [ ] reviewed by a deaf NSL advisor; set `validated_by_native_signer = true`
