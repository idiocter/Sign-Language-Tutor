"""Compile data/vocabulary.csv -> data/sign_dictionary.json (validated).

Run from the ml/ directory:

    python scripts/build_dictionary.py
"""

from __future__ import annotations

from signbridge.config import DICTIONARY_PATH
from signbridge.schema import save_dictionary
from signbridge.vocabulary import build_dictionary


def main() -> None:
    d = build_dictionary()
    save_dictionary(d, DICTIONARY_PATH)
    print(f"wrote {len(d.signs)} signs -> {DICTIONARY_PATH.relative_to(DICTIONARY_PATH.parents[1])}")
    ready = d.ready_for_training()
    print(f"signs ready for training (>=5 signers): {len(ready)} / {len(d.signs)}")


if __name__ == "__main__":
    main()
