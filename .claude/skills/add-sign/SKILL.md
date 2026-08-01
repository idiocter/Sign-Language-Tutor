---
name: add-sign
description: Add a new NSL sign to the vocabulary and rebuild the sign dictionary. Use when asked to add/define a sign, extend the vocabulary, or create a new NSL_dddd entry.
---

# Add an NSL sign

Adds a row to `ml/data/vocabulary.csv` and regenerates `ml/data/sign_dictionary.json`.

## Rules (non-negotiable — see Guide/files/PROJECT_PLAN.md)

- **Language-neutral ID.** The `sign_id` must be the next free `NSL_dddd` (zero-padded).
  Never key a sign by its English word. `schema.Sign` rejects anything else.
- **Both labels required.** `en` and Devanagari `ne` are mandatory; add `ne_roman` too so
  transliteration and search work.
- **Mark it unvalidated.** New signs are `validated_by_native_signer = false` until a deaf
  NSL advisor confirms the phonology. Say so in your summary — do not imply it is verified.

## Steps

1. Find the highest existing `sign_id` in `ml/data/vocabulary.csv`; the new one is +1.
2. Append a row with all columns:
   `sign_id,en,ne,ne_roman,gloss_code,handshape,location,movement,orientation,two_handed,symmetric,eyebrows,head,category,difficulty,phase,prerequisites`
   - `gloss_code`: UPPERCASE symbolic gloss (e.g. `THANK-YOU`).
   - phonology (`handshape/location/movement/orientation`): best-effort; flag for review.
   - `prerequisites`: semicolon-separated sign_ids, or empty.
3. Rebuild + validate:
   ```bash
   cd ml && ./.venv/bin/python scripts/build_dictionary.py
   ./.venv/bin/pytest -q tests/test_schema.py
   ```
4. Report the new `sign_id`, that it needs native-signer validation, and any phonology
   fields you guessed.
