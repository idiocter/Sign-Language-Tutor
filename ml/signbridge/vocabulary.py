"""Load the core vocabulary CSV into validated :class:`Sign` objects.

``data/vocabulary.csv`` is the human-editable Phase 0 deliverable — one row per sign, easy
for advisors to review in a spreadsheet. :func:`build_dictionary` compiles it into the
canonical ``sign_dictionary.json`` that models and agents consume.

The CSV is a *seed*, not the finished 200. Real NSL vocabulary and phonology parameters
must be confirmed with deaf advisors (PROJECT_PLAN.md, Phase 0). Rows here are marked
``validated_by_native_signer = false`` until that review happens.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .config import VOCAB_PATH
from .schema import Curriculum, Labels, NonManualMarkers, Parameters, Sign, SignDictionary


def _split_prereqs(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(";") if p.strip()]


def _as_bool(raw: str) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "y"}


def load_rows(path: Path | str = VOCAB_PATH) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def row_to_sign(row: dict[str, str]) -> Sign:
    return Sign(
        sign_id=row["sign_id"].strip(),
        labels=Labels(
            en=row["en"].strip(),
            ne=row["ne"].strip(),
            ne_roman=(row.get("ne_roman") or "").strip() or None,
        ),
        gloss_code=row["gloss_code"].strip(),
        parameters=Parameters(
            handshape=row["handshape"].strip(),
            location=row["location"].strip(),
            movement=row["movement"].strip(),
            orientation=row["orientation"].strip(),
            two_handed=_as_bool(row.get("two_handed", "")),
            symmetric=_as_bool(row.get("symmetric", "")),
        ),
        non_manual_markers=NonManualMarkers(
            eyebrows=(row.get("eyebrows") or "neutral").strip() or None,
            head=(row.get("head") or "neutral").strip() or None,
        ),
        curriculum=Curriculum(
            difficulty=int(row.get("difficulty") or 1),
            category=(row.get("category") or "").strip() or None,
            phase=int(row["phase"]) if row.get("phase") else None,
            prerequisites=_split_prereqs(row.get("prerequisites", "")),
        ),
        clip_ref=f"clips/{row['sign_id'].strip().lower()}.glb",
        reference_landmarks=f"refs/{row['sign_id'].strip().lower()}.npy",
    )


def build_dictionary(path: Path | str = VOCAB_PATH, version: str = "0.1.0") -> SignDictionary:
    """Compile the vocabulary CSV into a validated :class:`SignDictionary`."""
    signs = [row_to_sign(r) for r in load_rows(path)]
    ids = [s.sign_id for s in signs]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate sign_id(s) in vocabulary: {sorted(dupes)}")
    return SignDictionary(version=version, sign_language="NSL", signs=signs)
