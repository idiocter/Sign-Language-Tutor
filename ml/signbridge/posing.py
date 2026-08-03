"""Map sign phonology to a procedural pose spec and an ARKit facial track.

Phase 2 is **clip-based** (TECH_STACK.md Layer 3): the real avatar plays one authored glTF
clip per sign. Those clips don't exist yet — they take a rigged Blender character with ARKit
blendshapes and an animator working with deaf advisors. Until then, this derives a
*procedural* pose from each sign's `parameters` so the avatar can sign every sign now, as a
clearly-labelled placeholder. The `clip_ref` seam means an authored `.glb` overrides the
procedural pose the moment it's dropped in.

Coordinates are in the avatar's local signing space: origin at mid-chest, +x = signer's
left→right, +y = up, +z = forward (toward the viewer). Units are roughly metres.

Nothing here is anatomically exact. It is a legible stand-in, not motion-captured NSL.
"""

from __future__ import annotations

# --- Location anchors: where the dominant hand sits for a sign ---------------
LOCATION_ANCHORS: dict[str, tuple[float, float, float]] = {
    "neutral_space": (0.22, -0.05, 0.35),
    "chest_center": (0.0, 0.0, 0.20),
    "chest": (0.0, 0.0, 0.20),
    "chin": (0.0, 0.34, 0.20),
    "mouth": (0.0, 0.38, 0.18),
    "face": (0.10, 0.42, 0.18),
    "forehead": (0.0, 0.55, 0.18),
    "head": (0.0, 0.52, 0.15),
    "head_side": (0.26, 0.50, 0.10),
    "open_palm": (-0.16, -0.05, 0.30),
}
_DEFAULT_ANCHOR = (0.22, -0.05, 0.35)


# --- Handshape -> overall finger curl (0 = flat/open, 1 = closed fist) --------
def handshape_curl(handshape: str) -> float:
    h = handshape.lower()
    if "fist" in h:
        return 1.0
    if "claw" in h:
        return 0.6
    if "curved" in h:
        return 0.4
    if h.startswith("flat") or "5" in h or "open" in h:
        return 0.1
    if "thumb" in h:
        return 0.8
    if "pinch" in h or h.startswith("hand_"):
        return 0.35
    if "index" in h or h.startswith("hand_3") or h.startswith("hand_4"):
        return 0.5
    return 0.35


# --- Orientation -> palm-normal direction ------------------------------------
_ORIENTATION_NORMALS: dict[str, tuple[float, float, float]] = {
    "palm_forward": (0.0, 0.0, 1.0),
    "palm_inward": (0.0, 0.0, -1.0),
    "palm_down": (0.0, -1.0, 0.0),
    "palm_up": (0.0, 1.0, 0.0),
    "palm_side": (1.0, 0.0, 0.0),
    "palm_facing": (1.0, 0.0, 0.0),
}


def orientation_normal(orientation: str) -> tuple[float, float, float]:
    return _ORIENTATION_NORMALS.get(orientation.lower(), (0.0, 0.0, 1.0))


# --- Movement -> a descriptor the player animates around the anchor ----------
def movement_descriptor(movement: str) -> dict:
    m = movement.lower()

    def d(kind: str, amp: float = 0.06, repeats: int = 1) -> dict:
        return {"kind": kind, "amplitude": amp, "repeats": repeats}

    if "static" in m or not m:
        return d("static", 0.0)
    if "tap" in m:
        return d("tap", 0.04, 2 if "twice" in m or "repeat" in m else 1)
    if "arc" in m or "outward" in m or "flick" in m:
        return d("arc", 0.10)
    if "circle" in m or "circular" in m:
        return d("circle", 0.06)
    if "side" in m or "shake" in m:
        return d("oscillate_x", 0.08, 2)
    if any(k in m for k in ("down", "droop", "slide", "press")):
        return d("down", 0.10)
    if any(k in m for k in ("up", "lift", "scoop", "brush", "rotate", "tilt", "draw")):
        return d("up", 0.10)
    if "wave" in m:
        return d("wave", 0.08, 2)
    if "tremble" in m or "shiver" in m or "squeeze" in m:
        return d("tremble", 0.03, 3)
    if "expand" in m or "narrow" in m or "scale" in m:
        return d("scale", 0.10)
    if "twist" in m:
        return d("twist", 0.08)
    if any(k in m for k in ("interlock", "cross", "roof", "clap", "together", "meet")):
        return d("meet", 0.10)
    return d("arc", 0.08)


def _mirror(p: tuple[float, float, float]) -> tuple[float, float, float]:
    return (-p[0], p[1], p[2])


def pose_for(parameters) -> dict:
    """Build a procedural pose spec from a sign's `Parameters`.

    Returns a JSON-serializable dict the frontend renders directly.
    """
    anchor = LOCATION_ANCHORS.get(parameters.location.lower(), _DEFAULT_ANCHOR)
    curl = handshape_curl(parameters.handshape)
    normal = orientation_normal(parameters.orientation)
    movement = movement_descriptor(parameters.movement)

    right = {
        "location": list(anchor),
        "location_label": parameters.location,
        "movement_label": parameters.movement,
        "handshape": parameters.handshape,
        "curl": curl,
        "palm_normal": list(normal),
    }
    pose = {
        "two_handed": bool(parameters.two_handed),
        "symmetric": bool(parameters.symmetric),
        "movement": movement,
        "right_hand": right,
        "left_hand": None,
        "procedural": True,  # flips to False when an authored clip drives the sign
    }
    if parameters.two_handed:
        left_anchor = _mirror(anchor) if parameters.symmetric else LOCATION_ANCHORS["open_palm"]
        left_normal = _mirror(normal) if parameters.symmetric else (1.0, 0.0, 0.0)
        pose["left_hand"] = {
            "location": list(left_anchor),
            "handshape": parameters.handshape,
            "curl": curl,
            "palm_normal": list(left_normal),
        }
    return pose
