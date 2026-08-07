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

import re

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


# --- Handshape -> per-finger articulation ------------------------------------
# A handshape is not a single "how closed" scalar: a pointing "D", a spread "V", an "F" ring
# and a fist are equally closed on average yet look nothing alike. Rendering them accurately
# needs PER-FINGER flexion plus finger spread and a thumb configuration. This inventory,
# keyed by handshape identity (the letter/number after the family prefix — "index_D" -> "d",
# "flat_5" -> "5", "hand_W" -> "w"), is the backend's source of truth; the avatar applies it.
#
# Finger order everywhere: [thumb, index, middle, ring, pinky].
# curl: 0 = straight/extended, 1 = folded into the palm. spread: 0 = together, 1 = full splay.
# thumb_out: 0 = tucked/across the palm, 1 = fully out to the side.

_HANDSHAPES: dict[str, dict] = {
    # closed / fist
    "s": {"curl": [0.85, 1, 1, 1, 1], "spread": 0.0, "thumb_out": 0.1},
    "a": {"curl": [0.2, 1, 1, 1, 1], "spread": 0.0, "thumb_out": 0.5},
    # flat / open
    "b": {"curl": [0.7, 0.02, 0.02, 0.02, 0.02], "spread": 0.0, "thumb_out": 0.0},
    "5": {"curl": [0.1, 0.05, 0.05, 0.05, 0.05], "spread": 1.0, "thumb_out": 1.0},
    "4": {"curl": [0.95, 0.02, 0.02, 0.02, 0.02], "spread": 0.8, "thumb_out": 0.0},
    "o": {"curl": [0.55, 0.6, 0.6, 0.6, 0.6], "spread": 0.0, "thumb_out": 0.55},
    "c": {"curl": [0.35, 0.4, 0.4, 0.42, 0.45], "spread": 0.25, "thumb_out": 0.6},
    # pointing / index family
    "d": {"curl": [0.55, 0.02, 0.85, 0.95, 0.95], "spread": 0.0, "thumb_out": 0.2},
    "1": {"curl": [0.8, 0.02, 1, 1, 1], "spread": 0.0, "thumb_out": 0.1},
    "u": {"curl": [0.85, 0.02, 0.02, 1, 1], "spread": 0.0, "thumb_out": 0.0},
    "v": {"curl": [0.85, 0.02, 0.02, 1, 1], "spread": 1.0, "thumb_out": 0.0},
    "2": {"curl": [0.85, 0.02, 0.02, 1, 1], "spread": 1.0, "thumb_out": 0.0},
    "hook": {"curl": [0.7, 0.55, 1, 1, 1], "spread": 0.0, "thumb_out": 0.3},
    "x": {"curl": [0.7, 0.55, 1, 1, 1], "spread": 0.0, "thumb_out": 0.3},
    # thumb-and-finger contacts
    "f": {"curl": [0.5, 0.55, 0.02, 0.02, 0.02], "spread": 0.5, "thumb_out": 0.4},
    "9": {"curl": [0.5, 0.55, 0.02, 0.02, 0.02], "spread": 0.5, "thumb_out": 0.4},
    "g": {"curl": [0.2, 0.02, 1, 1, 1], "spread": 0.0, "thumb_out": 0.75},
    "l": {"curl": [0.05, 0.02, 1, 1, 1], "spread": 0.0, "thumb_out": 1.0},
    "w": {"curl": [0.85, 0.02, 0.02, 0.02, 1], "spread": 0.7, "thumb_out": 0.2},
    "6": {"curl": [0.85, 0.02, 0.02, 0.02, 1], "spread": 0.5, "thumb_out": 0.2},
    "3": {"curl": [0.1, 0.02, 0.02, 1, 1], "spread": 0.5, "thumb_out": 1.0},
    "7": {"curl": [0.6, 0.02, 0.02, 0.9, 0.02], "spread": 0.35, "thumb_out": 0.4},
    "8": {"curl": [0.5, 0.02, 0.85, 0.02, 0.02], "spread": 0.35, "thumb_out": 0.4},
    # thumb extended (10)
    "up": {"curl": [0.05, 1, 1, 1, 1], "spread": 0.0, "thumb_out": 0.85},
    "down": {"curl": [0.05, 1, 1, 1, 1], "spread": 0.0, "thumb_out": 0.85},
}

_HANDSHAPE_FAMILIES: dict[str, str] = {
    "fist": "s",
    "flat": "b",
    "index": "1",
    "curved": "c",
    "pinch": "f",
    "thumb": "up",
    "hand": "5",
}
_CLAW = {"curl": [0.35, 0.45, 0.45, 0.45, 0.45], "spread": 1.0, "thumb_out": 0.6}


def handshape_articulation(handshape: str) -> dict:
    """Resolve a handshape label to per-finger articulation (see `_HANDSHAPES`)."""
    h = (handshape or "").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", h) if t]

    base: dict | None = None
    for t in tokens:  # a specific identity (letter/number) wins over the family prefix
        if t in _HANDSHAPES:
            base = _HANDSHAPES[t]
            break
    if base is None:
        if "claw" in h:
            base = _CLAW
        else:
            for t in tokens:
                if t in _HANDSHAPE_FAMILIES:
                    base = _HANDSHAPES[_HANDSHAPE_FAMILIES[t]]
                    break
    if base is None:
        base = {"curl": [0.25, 0.25, 0.25, 0.25, 0.25], "spread": 0.2, "thumb_out": 0.4}

    curl = list(base["curl"])
    spread = base["spread"]
    thumb_out = base["thumb_out"]
    if "claw" in h and base is not _CLAW:  # round extended fingers into a curve
        curl = [max(c, 0.45) for c in curl]
        thumb_out = max(thumb_out, 0.5)
    return {"curl": curl, "spread": spread, "thumb_out": thumb_out}


def handshape_curl(handshape: str) -> float:
    """Overall closedness (0 = open, 1 = fist) — the mean per-finger flexion. Kept for
    callers that only need a scalar; the avatar uses the full per-finger articulation."""
    curl = handshape_articulation(handshape)["curl"]
    return round(sum(curl) / len(curl), 3)


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
    articulation = handshape_articulation(parameters.handshape)
    curl = round(sum(articulation["curl"]) / 5, 3)
    normal = orientation_normal(parameters.orientation)
    movement = movement_descriptor(parameters.movement)

    right = {
        "location": list(anchor),
        "location_label": parameters.location,
        "movement_label": parameters.movement,
        "handshape": parameters.handshape,
        "curl": curl,  # scalar mean, kept for backward compatibility
        "fingers": articulation["curl"],  # per-finger flexion [thumb..pinky]
        "spread": articulation["spread"],
        "thumb_out": articulation["thumb_out"],
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
            "fingers": articulation["curl"],
            "spread": articulation["spread"],
            "thumb_out": articulation["thumb_out"],
            "palm_normal": list(left_normal),
        }
    return pose
