# SignBridge — Project Plan

Bilingual (English + Nepali) sign language tutor and interpreter with an animated avatar.

---

## Scope Lock

**In scope**
- NSL (Nepali Sign Language) as the target sign language
- English + Nepali as spoken/written languages
- Isolated sign recognition (webcam → sign)
- Devanagari fingerspelling recognition
- Avatar-based sign production (text → animated signing)
- Tutor loop: curriculum, practice, scoring, feedback

**Out of scope for v1**
- ASL as a user-facing output (used only as pretraining data)
- Full continuous sign translation (sentence-level, unconstrained)
- Real-time two-way video calling

**Non-negotiable**
Deaf NSL signers involved from Phase 0, not as testers at the end.

---

## Phase 0 — Foundation (3 weeks)

Everything here is cheap to do now and expensive to retrofit.

| Task | Deliverable |
|---|---|
| Recruit 2–3 deaf NSL signers as advisors | Signed agreement, consultation schedule |
| Define 200-sign core vocabulary | `vocabulary.csv` with sign IDs |
| Lock the sign schema (language-neutral IDs) | `sign_schema.json` |
| Build the capture tool | `capture_tool.py` running, saving `.npy` |
| Roman → Devanagari transliteration prototype | Working function, 90%+ on test set |
| Repo, CI, project board | GitHub repo scaffolded |

**Exit criteria:** you can record a sign, and it lands on disk as a normalized landmark array tagged with a language-neutral ID.

---

## Phase 1 — Recognition MVP (6 weeks)

| Week | Work |
|---|---|
| 1–2 | Data collection sprint: 50 signs × 30 samples × ≥5 signers |
| 3 | Preprocessing pipeline: normalization, augmentation, train/val/test split **by signer** |
| 4–5 | Transformer encoder on landmark sequences; pretrain on WLASL, fine-tune on NSL |
| 6 | Export to ONNX, browser inference, live demo page |

**Exit criteria:** ≥85% top-1 accuracy on held-out *signers* (not held-out clips), running in-browser at ≥15 FPS.

**Failure mode to avoid:** splitting by clip instead of signer. It inflates accuracy by 15–25 points and the model collapses on real users.

---

## Phase 1.5 — Fingerspelling (2 weeks)

Separate, simpler model. Static handshape classification for the Devanagari manual alphabet (~36 consonants + vowel signs).

- Single-frame CNN (MobileNetV3) on cropped hand region
- 100+ samples per character
- **Exit criteria:** ≥90% top-1, works for spelling out names and loanwords

---

## Phase 2 — Avatar Pipeline (4 weeks)

| Week | Work |
|---|---|
| 1 | Rig sourced and prepared in Blender; ARKit blendshapes verified |
| 2 | Clip authoring workflow — one pose clip per sign, 50 signs |
| 3 | glTF export + three.js player with co-articulation blending |
| 4 | Facial track: eyebrow raise, mouth morphemes, head tilt |

**Exit criteria:** deaf advisors rate ≥4/5 on intelligibility for 20 randomly selected signs. If the face is static, this phase is not done regardless of hand accuracy.

---

## Phase 3 — Tutor Loop (4 weeks)

- FSRS spaced repetition scheduling
- DTW scoring on normalized joint angles → per-joint error decomposition
- Curriculum Agent (lesson sequencing) + Critique Agent (corrective feedback)
- Nepali feedback via slot-filled templates; English via LLM
- Bikram Sambat calendar for streaks and schedules

**Exit criteria:** a new user can complete a 10-sign lesson, receive specific corrective feedback in their chosen language, and return to a correctly scheduled review.

---

## Phase 4 — Interpreter Mode (7 weeks)

Two independent workstreams — run them in parallel if you have help.

**Workstream A — Sign → Language (3 weeks)**
- Continuous recognition with CTC head
- Sign sequence → gloss → Nepali/English text
- TTS output

**Workstream B — Language → Sign (4 weeks)**
- Nepali ASR: fine-tune Whisper on OpenSLR SLR43 + Common Voice
- Text → gloss (Gloss Translation Agent, language-pair aware)
- Gloss → Animation Director → avatar playback

**Exit criteria:** constrained-domain conversation (greetings, directions, basic needs) works end-to-end in both directions. Text input always available as fallback when ASR fails.

---

## Phase 5 — Evaluation & Deploy (3 weeks)

- Signer-independent test set, never touched during development
- WER for continuous recognition
- **Avatar intelligibility rated by native signers** — the metric that actually matters
- Separate usability testing for Nepali-dominant vs English-comfortable deaf users
- Deploy: Vercel (frontend), Railway/Fly.io (backend), Cloudflare R2 (assets)

---

## Final Goals

By the end of the project you should be able to demonstrate:

1. **Recognition** — 200 NSL signs recognized from webcam, ≥85% on unseen signers, running in-browser with no video leaving the device.
2. **Fingerspelling** — Devanagari manual alphabet recognized at ≥90%.
3. **Production** — An avatar that signs 200 NSL signs with facial grammar, rated intelligible by native signers.
4. **Teaching** — A working spaced-repetition tutor giving specific, joint-level corrective feedback in English and Nepali.
5. **Interpreting** — Bidirectional constrained-domain interpretation between NSL and both Nepali and English.
6. **Bilingual throughout** — Devanagari input with Romanized transliteration, Nepali TTS, BS calendar, full UI localization.
7. **Community-validated** — Built with deaf NSL signers, with documented evaluation from them.

---

## Total Timeline

**29 weeks** (~7 months) at full-time pace. Realistically 9–10 months alongside coursework.

If you need to cut scope, cut in this order:
1. Phase 4 Workstream A (continuous recognition) — hardest, least reliable
2. Nepali TTS (ship text-only output)
3. Vocabulary 200 → 100

Never cut: Phase 0 schema work, signer-independent splits, or deaf community involvement.
