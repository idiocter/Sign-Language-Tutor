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

### Make the avatar look like you (from a selfie)

Photo → 3D face can't be done in this repo's code; use an avatar generator, then plug the
result into the seam above:

1. Go to **[readyplayer.me](https://readyplayer.me)** → **Create Avatar** → upload a
   front-facing selfie. It builds a rigged 3D head+body that resembles you, **with ARKit
   blendshapes** (which our facial track already targets — see `ml/signbridge/facial.py`).
2. Download the **`.glb`** (full-body). Save it as `web/public/avatar/character.glb`.
3. That's it — the loader is already wired. `SigningAvatar.tsx` HEAD-checks for
   `web/public/avatar/character.glb` on mount and, if present, loads it automatically with
   drei's `useGLTF`, driving its arm/finger bones from the same keyframe/IK data and its face
   from the ARKit blendshapes. No localStorage or URL needed. A pasted Ready Player Me URL
   (the "👤 Use my avatar" button) still works as an override. If a model fails to load, a
   visible notice appears instead of silently reverting to the stand-in. (Arm/finger
   retargeting is model-specific and may need tuning once your model is in place.)

Until then, `SigningAvatar.tsx` renders a **stylized** figure (tan skin, dark swept hair
with an undercut, light stubble) — a nod to the reference look, not a photo likeness.
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
