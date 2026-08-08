"""The recursive learning loop: learner attempts become training data, which retrains the
model, which scores the next attempts better.

    capture → score (DTW) + recognize (ONNX) → gate → stage as candidate
        → human review → promote into data/raw/ → retrain → better model → …

Each turn of that loop is a **generation**. The counter in ``flywheel_state.json`` makes
the recursion auditable: every promoted take records the model generation that admitted
it, so a regression can be traced to the generation that let bad data in.

Three rules keep the loop from eating itself:

1. **Nothing enters training without a human.** The gate only produces *candidates*. A
   reviewer approves them; :func:`CandidateStore.promote` moves only approved ones. This
   is the same rule the vocabulary scraper follows.
2. **Learner data augments, never founds, a class.** A sign needs
   ``min_studio_signers`` distinct non-learner signers in ``data/raw/`` before any
   learner-contributed take is promoted for it. Otherwise the model would be learning a
   sign from the very predictions it made about that sign.
3. **No signer may dominate.** A per-signer share cap protects the signer-independent
   split (PROJECT_PLAN.md's named failure mode). A flywheel fed mostly by one enthusiastic
   learner produces a model that works for exactly one person.

Storage is plain files — ``data/candidates/<sign_id>/<candidate_id>.npy`` plus a ``.json``
sidecar holding the metadata. The sidecar is the source of truth, so the promotion step
runs offline with no database and the ml package stays independent of the API.

Torch-free: numpy + stdlib only.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .agents.data_curator import DataCuratorAgent
from .config import DATA_DIR, FEATURE_DIM, RAW_DIR
from .preprocessing import discover

CANDIDATES_DIR = DATA_DIR / "candidates"
STATE_FILENAME = "flywheel_state.json"

# A learner-contributed take is only worth training on if the learner produced the sign
# well *and* the model already recognizes it confidently. Either signal alone is too weak:
# a high DTW score against a noisy reference, or a confident prediction of the wrong sign,
# both poison the pool.
DEFAULT_MIN_SCORE = 85.0
DEFAULT_MIN_CONFIDENCE = 0.90

# Promotion guards (see the module docstring).
DEFAULT_MIN_STUDIO_SIGNERS = 2
DEFAULT_MAX_SIGNER_SHARE = 0.4

STATUSES = ("pending", "approved", "rejected", "promoted")

# Signer IDs must not contain "_" — preprocessing._NAME_RE splits fields on a double
# underscore, so a signer ID with one in it would silently corrupt the parsed sign/signer.
_SLUG_RE = re.compile(r"[^A-Za-z0-9-]+")


def contributor_signer_id(contributor: str) -> str:
    """``"learner-7"`` → ``"Llearner-7"``.

    The ``L`` prefix keeps learner-contributed signers in a namespace of their own, so they
    can never collide with a studio signer ID (``S01``…) and the split stays honest.
    """
    slug = _SLUG_RE.sub("-", str(contributor)).strip("-").lower()
    if not slug:
        raise ValueError(f"contributor {contributor!r} has no usable characters for a signer ID")
    return f"L{slug}"


def is_learner_signer(signer_id: str) -> bool:
    return signer_id.startswith("L")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stamp(offset_seconds: int = 0) -> str:
    ts = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return ts.strftime("%Y%m%d_%H%M%S")


# --- Types ------------------------------------------------------------------

@dataclass
class GateDecision:
    """Why an attempt was or wasn't kept. Rejections are explained, never silent."""

    accepted: bool
    reasons: list[str] = field(default_factory=list)   # rejection causes
    flags: list[str] = field(default_factory=list)     # curator quality flags

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Candidate:
    candidate_id: str
    sign_id: str
    signer_id: str
    contributor: str
    score: float
    confidence: float
    status: str = "pending"
    flags: list[str] = field(default_factory=list)
    generation: int = 0                 # model generation that admitted this attempt
    created_at: str = field(default_factory=_utcnow)
    reviewed_by: str | None = None
    review_note: str | None = None
    reviewed_at: str | None = None
    promoted_at: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class PromotionResult:
    promoted: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (candidate_id, reason)
    generation: int = 0
    dry_run: bool = False

    def as_dict(self) -> dict:
        return {
            "promoted": self.promoted,
            "skipped": [{"candidate_id": c, "reason": r} for c, r in self.skipped],
            "generation": self.generation,
            "dry_run": self.dry_run,
        }


# --- Gate -------------------------------------------------------------------

def gate(
    sequence: np.ndarray,
    *,
    sign_id: str,
    score: float,
    confidence: float,
    recognized_sign_id: str | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    curator: DataCuratorAgent | None = None,
) -> GateDecision:
    """Decide whether a scored attempt is worth keeping as a training candidate.

    ``score`` is the DTW overall (0–100) against the sign's reference; ``confidence`` is
    the recognition model's probability for its top class, and ``recognized_sign_id`` that
    class. Passing the gate makes an attempt a *candidate* — never training data.
    """
    reasons: list[str] = []

    seq = np.asarray(sequence, dtype=np.float32)
    if seq.ndim != 2 or seq.shape[1] != FEATURE_DIM:
        return GateDecision(False, [f"bad_shape:{seq.shape}"], [])

    if score < min_score:
        reasons.append(f"score_below_{min_score:g}")
    if confidence < min_confidence:
        reasons.append(f"confidence_below_{min_confidence:g}")
    if recognized_sign_id is not None and recognized_sign_id != sign_id:
        # The learner meant one sign and the model saw another. Whoever is wrong, the
        # label is unreliable — exactly the take that would teach the model its own error.
        reasons.append(f"recognized_{recognized_sign_id}_not_{sign_id}")

    report = (curator or DataCuratorAgent()).run([(sign_id, seq)])[0]
    reasons.extend(report.flags)
    return GateDecision(accepted=not reasons, reasons=reasons, flags=list(report.flags))


# --- Candidate store --------------------------------------------------------

class CandidateStore:
    """File-backed store of gated attempts awaiting human review.

    ``root`` and ``raw_dir`` are injectable so tests (and a reviewer working on a copy)
    never touch the real dataset.
    """

    def __init__(self, root: Path | str = CANDIDATES_DIR, raw_dir: Path | str = RAW_DIR):
        self.root = Path(root)
        self.raw_dir = Path(raw_dir)

    # -- generation state --

    @property
    def state_path(self) -> Path:
        return self.root / STATE_FILENAME

    def state(self) -> dict:
        if not self.state_path.exists():
            return {"generation": 0, "history": []}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write_state(self, state: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    @property
    def generation(self) -> int:
        return int(self.state().get("generation", 0))

    # -- paths --

    def _sign_dir(self, sign_id: str) -> Path:
        return self.root / sign_id

    def _meta_path(self, candidate: Candidate) -> Path:
        return self._sign_dir(candidate.sign_id) / f"{candidate.candidate_id}.json"

    def sequence_path(self, candidate: Candidate) -> Path:
        return self._sign_dir(candidate.sign_id) / f"{candidate.candidate_id}.npy"

    # -- write --

    def stage(
        self,
        sequence: np.ndarray,
        *,
        sign_id: str,
        contributor: str,
        score: float,
        confidence: float,
        consent: bool,
        flags: list[str] | None = None,
    ) -> Candidate:
        """Persist a gated attempt as a pending candidate.

        ``consent`` must be an explicit True: this writes a recording of a person's body
        movement to disk, and the learner has to have agreed to that specifically.
        """
        if not consent:
            raise PermissionError("cannot stage a learner take without explicit consent")

        seq = np.asarray(sequence, dtype=np.float32)
        if seq.ndim != 2 or seq.shape[1] != FEATURE_DIM:
            raise ValueError(f"sequence must be (frames, {FEATURE_DIM}); got {seq.shape}")

        signer_id = contributor_signer_id(contributor)
        sign_dir = self._sign_dir(sign_id)
        # Two takes of the same sign by the same learner inside one second would collide.
        # Nudge the timestamp forward rather than the signer ID: a suffixed signer would
        # split one person into two, which is precisely what the signer-split forbids.
        offset = 0
        while (sign_dir / f"{sign_id}__{signer_id}__{_stamp(offset)}.npy").exists():
            offset += 1
        candidate_id = f"{sign_id}__{signer_id}__{_stamp(offset)}"

        candidate = Candidate(
            candidate_id=candidate_id,
            sign_id=sign_id,
            signer_id=signer_id,
            contributor=str(contributor),
            score=round(float(score), 2),
            confidence=round(float(confidence), 4),
            flags=list(flags or []),
            generation=self.generation,
        )
        sign_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.sequence_path(candidate), seq)
        self._meta_path(candidate).write_text(
            json.dumps(candidate.as_dict(), indent=2), encoding="utf-8"
        )
        return candidate

    # -- read --

    def list_candidates(
        self, *, status: str | None = None, sign_id: str | None = None
    ) -> list[Candidate]:
        if status is not None and status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
        if not self.root.exists():
            return []
        pattern = f"{sign_id}/*.json" if sign_id else "*/*.json"
        out: list[Candidate] = []
        for path in sorted(self.root.glob(pattern)):
            try:
                out.append(Candidate(**json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, TypeError):
                continue  # a half-written or hand-edited sidecar must not break review
        if status is not None:
            out = [c for c in out if c.status == status]
        return out

    def get(self, candidate_id: str) -> Candidate | None:
        for candidate in self.list_candidates():
            if candidate.candidate_id == candidate_id:
                return candidate
        return None

    def load_sequence(self, candidate: Candidate) -> np.ndarray:
        return np.load(self.sequence_path(candidate)).astype(np.float32)

    def duplicate_of(
        self,
        sequence: np.ndarray,
        *,
        sign_id: str,
        contributor: str,
        limit: int = 32,
        curator: DataCuratorAgent | None = None,
    ) -> str | None:
        """The already-staged take this one near-duplicates, if any.

        Repeating a single good attempt adds no information to the dataset but does add
        weight, so the flywheel would slowly overfit to whichever sign a keen learner
        happened to drill. Only the same contributor's takes are compared — two people
        signing the same sign well *should* look alike, and that is signal, not noise.
        """
        signer_id = contributor_signer_id(contributor)
        prior = [
            c
            for c in self.list_candidates(sign_id=sign_id)
            if c.signer_id == signer_id and c.status != "rejected"
        ][-limit:]
        if not prior:
            return None
        takes = [(c.candidate_id, self.load_sequence(c)) for c in prior]
        takes.append(("__new__", np.asarray(sequence, dtype=np.float32)))
        reports = (curator or DataCuratorAgent()).run(takes)
        return reports[-1].duplicate_of

    # -- review --

    def review(
        self, candidate_id: str, *, status: str, reviewer: str, note: str | None = None
    ) -> Candidate:
        if status not in ("approved", "rejected"):
            raise ValueError("review status must be 'approved' or 'rejected'")
        candidate = self.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        if candidate.status == "promoted":
            raise ValueError(f"{candidate_id} is already in the training set")
        candidate.status = status
        candidate.reviewed_by = reviewer
        candidate.review_note = note
        candidate.reviewed_at = _utcnow()
        self._meta_path(candidate).write_text(
            json.dumps(candidate.as_dict(), indent=2), encoding="utf-8"
        )
        return candidate

    # -- promote --

    def _raw_counts(self) -> tuple[dict[str, Counter], dict[str, set[str]]]:
        """Per-sign take counts by signer, and per-sign studio (non-learner) signers."""
        per_sign: dict[str, Counter] = defaultdict(Counter)
        studio: dict[str, set[str]] = defaultdict(set)
        for sample in discover(self.raw_dir):
            per_sign[sample.sign_id][sample.signer_id] += 1
            if not is_learner_signer(sample.signer_id):
                studio[sample.sign_id].add(sample.signer_id)
        return per_sign, studio

    def promote(
        self,
        *,
        min_studio_signers: int = DEFAULT_MIN_STUDIO_SIGNERS,
        max_signer_share: float = DEFAULT_MAX_SIGNER_SHARE,
        dry_run: bool = False,
    ) -> PromotionResult:
        """Move approved candidates into ``data/raw/`` and start the next generation.

        Skips (with a reason) any candidate that would breach the founding rule or the
        per-signer share cap. Candidate filenames already follow the capture tool's
        convention, so promotion is a copy — the training pipeline needs no changes.
        """
        per_sign, studio = self._raw_counts()
        result = PromotionResult(generation=self.generation, dry_run=dry_run)

        for candidate in self.list_candidates(status="approved"):
            counts = per_sign[candidate.sign_id]
            if len(studio[candidate.sign_id]) < min_studio_signers:
                result.skipped.append(
                    (
                        candidate.candidate_id,
                        f"only {len(studio[candidate.sign_id])} studio signer(s) for "
                        f"{candidate.sign_id}; need {min_studio_signers} before learner data",
                    )
                )
                continue

            projected_total = sum(counts.values()) + 1
            projected_signer = counts[candidate.signer_id] + 1
            if projected_signer / projected_total > max_signer_share:
                result.skipped.append(
                    (
                        candidate.candidate_id,
                        f"{candidate.signer_id} would hold "
                        f"{projected_signer}/{projected_total} of {candidate.sign_id} "
                        f"(cap {max_signer_share:.0%})",
                    )
                )
                continue

            if not dry_run:
                dest_dir = self.raw_dir / candidate.sign_id
                dest_dir.mkdir(parents=True, exist_ok=True)
                np.save(dest_dir / f"{candidate.candidate_id}.npy", self.load_sequence(candidate))
                candidate.status = "promoted"
                candidate.promoted_at = _utcnow()
                self._meta_path(candidate).write_text(
                    json.dumps(candidate.as_dict(), indent=2), encoding="utf-8"
                )
            counts[candidate.signer_id] += 1
            result.promoted.append(candidate.candidate_id)

        if result.promoted and not dry_run:
            state = self.state()
            state["generation"] = int(state.get("generation", 0)) + 1
            state.setdefault("history", []).append(
                {
                    "generation": state["generation"],
                    "at": _utcnow(),
                    "promoted": len(result.promoted),
                    "signs": sorted({c.split("__")[0] for c in result.promoted}),
                }
            )
            self._write_state(state)
            result.generation = state["generation"]
        return result

    # -- reporting --

    def readiness(self, dictionary=None, *, min_signers: int = 5) -> dict:
        """Where the loop stands: what's queued, and whether a retrain is worth running."""
        per_sign, studio = self._raw_counts()
        signs = (
            [s.sign_id for s in dictionary.signs] if dictionary is not None else sorted(per_sign)
        )
        ready = [s for s in signs if len(per_sign.get(s, {})) >= min_signers]
        by_status = Counter(c.status for c in self.list_candidates())
        state = self.state()
        last = state.get("history", [])[-1] if state.get("history") else None
        return {
            "generation": state.get("generation", 0),
            "last_promotion": last,
            "candidates": {status: by_status.get(status, 0) for status in STATUSES},
            "signs_ready_for_training": len(ready),
            "signs_total": len(signs),
            "min_signers": min_signers,
            # A retrain only pays for itself once approved data is actually waiting.
            "retrain_recommended": by_status.get("approved", 0) > 0,
            "learner_takes": sum(
                count
                for counts in per_sign.values()
                for signer, count in counts.items()
                if is_learner_signer(signer)
            ),
        }
