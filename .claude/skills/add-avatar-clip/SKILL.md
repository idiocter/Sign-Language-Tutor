---
name: add-avatar-clip
description: Wire an authored glTF sign clip into the avatar, or explain how to author one. Use when adding/replacing a sign's animation, dropping in a .glb, or asked about the avatar signing / facial track.
---

# Add an avatar clip

Replaces a sign's procedural placeholder motion with an authored glTF clip. The full
Blender + ARKit workflow is in `docs/avatar-authoring.md` — read it before authoring.

## If a `.glb` already exists

1. Confirm it is named by the language-neutral sign id, lowercased:
   `web/public/clips/nsl_dddd.glb` (must match the sign's `clip_ref`).
2. Verify it registers — no code change is needed:
   ```bash
   curl -s localhost:8000/clips/manifest | python3 -m json.tool | grep -A2 nsl_dddd
   ```
   The sign should show `"status": "authored"`. `/produce` will then set its `clip_ref`
   and the avatar plays the clip instead of the procedural pose.

## Guardrails (from PROJECT_PLAN.md Phase 2)

- **The face must move.** A clip with a static face fails the phase. Author the eyebrow /
  mouth / head track using the ARKit blendshape names in `ml/signbridge/facial.py`.
- Use the **language-neutral id** for the filename — never an English word.
- A clip is not done until a **deaf NSL advisor** reviews it; then set
  `validated_by_native_signer = true` on the sign.
- `.glb` files are gitignored — they are assets, not source.

## Where the seam is (for code changes)

- Procedural pose: `ml/signbridge/posing.py` + `ml/signbridge/facial.py`
- Plan assembly: `ml/signbridge/agents/animation.py`
- Player: `web/src/components/SigningAvatar.tsx` (authored-clip branch uses drei `useGLTF`)
