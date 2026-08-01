"""Non-manual markers -> ARKit blendshape coefficients + head motion.

Facial grammar carries meaning in sign language — it is not decoration. PROJECT_PLAN.md
Phase 2: "If the face is static, this phase is not done regardless of hand accuracy."

We target the **ARKit 52 blendshape space** on purpose: the MediaPipe face landmarker
outputs these same coefficients (DOWNLOADS.md), so the recognition side and the avatar side
speak the same 52-parameter language. A real Blender/Ready-Player-Me rig with ARKit
blendshapes consumes this dict directly; the placeholder avatar approximates a subset.
"""

from __future__ import annotations

# The 52 ARKit blendshape names (ARFaceAnchor.BlendShapeLocation), for reference and so a
# real rig can be driven by name. We only set the few that carry NSL grammar.
ARKIT_BLENDSHAPES = [
    "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
    "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft", "eyeLookDownRight",
    "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight",
    "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight",
    "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft", "jawOpen", "jawRight",
    "mouthClose", "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft", "mouthFrownRight",
    "mouthFunnel", "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft",
    "mouthPressRight", "mouthPucker", "mouthRight", "mouthRollLower", "mouthRollUpper",
    "mouthShrugLower", "mouthShrugUpper", "mouthSmileLeft", "mouthSmileRight",
    "mouthStretchLeft", "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight",
    "noseSneerLeft", "noseSneerRight", "tongueOut",
]

_EYEBROWS = {
    "raised": {"browInnerUp": 0.85, "browOuterUpLeft": 0.6, "browOuterUpRight": 0.6},
    "furrowed": {"browDownLeft": 0.7, "browDownRight": 0.7, "browInnerUp": 0.15},
    "neutral": {},
}


def _mouth(morpheme: str | None) -> dict[str, float]:
    if not morpheme:
        return {}
    m = morpheme.lower()
    if "smile" in m:
        return {"mouthSmileLeft": 0.6, "mouthSmileRight": 0.6}
    if "open" in m or m in {"aa", "ah"}:
        return {"jawOpen": 0.5}
    if m in {"oo", "ou"} or "pucker" in m or "funnel" in m:
        return {"mouthPucker": 0.7, "mouthFunnel": 0.3}
    if m in {"mm", "closed"} or "press" in m:
        return {"mouthPressLeft": 0.5, "mouthPressRight": 0.5, "mouthClose": 0.3}
    if m in {"th", " th"}:
        return {"tongueOut": 0.4, "jawOpen": 0.2}
    return {}


# head marker -> (static tilt in radians, animated gesture the player loops)
_HEAD = {
    "tilt_forward": ((0.20, 0.0, 0.0), None),
    "tilt_back": ((-0.20, 0.0, 0.0), None),
    "nod": ((0.0, 0.0, 0.0), "nod"),
    "shake": ((0.0, 0.0, 0.0), "shake"),
    "neutral": ((0.0, 0.0, 0.0), None),
}


def track_for(nmm) -> dict:
    """Build a facial track from a sign's `NonManualMarkers` (or None)."""
    blendshapes: dict[str, float] = {}
    head_rotation = [0.0, 0.0, 0.0]
    head_gesture = None

    if nmm is not None:
        if nmm.eyebrows:
            blendshapes.update(_EYEBROWS.get(nmm.eyebrows, {}))
        blendshapes.update(_mouth(nmm.mouth_morpheme))
        if nmm.head:
            (hx, hy, hz), gesture = _HEAD.get(nmm.head, ((0.0, 0.0, 0.0), None))
            head_rotation = [hx, hy, hz]
            head_gesture = gesture

    return {
        "blendshapes": blendshapes,          # ARKit coefficients, 0..1
        "head_rotation": head_rotation,      # static tilt, radians [x, y, z]
        "head_gesture": head_gesture,        # "nod" | "shake" | None (player loops it)
        "static": not blendshapes and head_gesture is None and head_rotation == [0.0, 0.0, 0.0],
    }
