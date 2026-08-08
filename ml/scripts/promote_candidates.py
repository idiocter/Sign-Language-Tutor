"""Promote approved learner takes into the training set — one turn of the flywheel.

    python ml/scripts/promote_candidates.py --report        # where does the loop stand?
    python ml/scripts/promote_candidates.py                 # dry run: what would move
    python ml/scripts/promote_candidates.py --apply         # actually move it

Approval happens elsewhere (a reviewer, via ``POST /flywheel/review/{id}``). This script
only moves what a human already signed off on, and refuses anything that would breach the
guards in :mod:`signbridge.flywheel`. Retrain after it runs:

    python ml/scripts/train_lite.py     # or train.py for the full model
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signbridge.flywheel import (  # noqa: E402
    DEFAULT_MAX_SIGNER_SHARE,
    DEFAULT_MIN_STUDIO_SIGNERS,
    CandidateStore,
)
from signbridge.vocabulary import build_dictionary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="move files (default: dry run)")
    parser.add_argument("--report", action="store_true", help="print status and exit")
    parser.add_argument("--min-studio-signers", type=int, default=DEFAULT_MIN_STUDIO_SIGNERS)
    parser.add_argument("--max-signer-share", type=float, default=DEFAULT_MAX_SIGNER_SHARE)
    args = parser.parse_args()

    store = CandidateStore()

    if args.report:
        report = store.readiness(build_dictionary())
        print(f"generation           {report['generation']}")
        print(f"candidates           {report['candidates']}")
        print(
            f"signs ready to train {report['signs_ready_for_training']}/{report['signs_total']}"
            f"  (>= {report['min_signers']} signers)"
        )
        print(f"learner takes in raw {report['learner_takes']}")
        print(f"retrain recommended  {report['retrain_recommended']}")
        return 0

    result = store.promote(
        min_studio_signers=args.min_studio_signers,
        max_signer_share=args.max_signer_share,
        dry_run=not args.apply,
    )
    verb = "would promote" if result.dry_run else "promoted"
    print(f"{verb} {len(result.promoted)} take(s)")
    for candidate_id in result.promoted:
        print(f"  + {candidate_id}")
    for candidate_id, reason in result.skipped:
        print(f"  - {candidate_id}: {reason}")
    if result.promoted and not result.dry_run:
        print(f"\ngeneration {result.generation} — retrain now: python ml/scripts/train_lite.py")
    elif result.dry_run and result.promoted:
        print("\nnothing moved (dry run). Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
