# SignBridge — Tech Stack

---

## Correction to your plan, up front

**OpenCV is not your landmark engine.** OpenCV handles camera capture, frame preprocessing, cropping, and drawing overlays. It does not give you hand or face landmarks.

**MediaPipe** gives you landmarks. Use both:

```
Camera → OpenCV (capture, resize, color convert)
       → MediaPipe (hand + pose + face landmarks)
       → your model
```

Also: you want **face landmark tracking**, not face *recognition*. Face recognition identifies who a person is. You need the 478-point face mesh to read eyebrow raise, mouth shape, and head tilt — these carry grammar in sign language, they are not decoration.

---

## Layer 1 — Vision Input

| Component | Choice | Why |
|---|---|---|
| Capture / preprocessing | OpenCV (`opencv-python`) | Frame handling, cropping, overlays |
| Landmark extraction | MediaPipe Tasks (Hand + Pose + Face Landmarker) | 21×2 hand pts, 33 pose pts, 478 face pts. CPU-fast, no GPU needed |
| Browser inference | MediaPipe Tasks JS + ONNX Runtime Web (WebGPU) | Video never leaves the device |

**Normalize landmarks before anything else.** Center on the shoulder midpoint, scale by shoulder width, and drop absolute pixel coords. Otherwise the model learns camera distance, not signs.

---

## Layer 2 — Recognition Models

| Task | Model | Notes |
|---|---|---|
| Isolated sign | Transformer encoder over landmark sequence (~5–10M params) | Trains on a single GPU or Colab |
| Alternative | ST-GCN | Exploits skeleton graph topology; try if Transformer plateaus |
| Fingerspelling | MobileNetV3 on cropped hand | Single-frame, no temporal model needed |
| Continuous (Phase 4) | Transformer + CTC head | Much harder — expect a real accuracy drop |
| Pretraining source | WLASL / MS-ASL | Skeleton features transfer across sign languages |

---

## Layer 3 — Avatar & Animation

| Component | Choice |
|---|---|
| Rigging | Blender 4.x |
| Base character | Mixamo (free, auto-rigged) or Ready Player Me |
| Facial rig | ARKit 52 blendshapes — **required**, not optional |
| Format | glTF / GLB |
| Web playback | three.js via react-three-fiber + drei |
| Blending | Custom co-articulation window between clips (~150–250ms crossfade) |

**Clip-based, not neural.** Author one pose clip per sign and blend transitions. Neural pose generation (Progressive Transformers, SignGAN) is still research-grade and produces unintelligible output.

---

## Layer 4 — Application

| Layer | Choice |
|---|---|
| Frontend | Next.js 15 + TypeScript |
| 3D | react-three-fiber, drei |
| State | Zustand |
| Styling | TailwindCSS |
| i18n | next-intl |
| Fonts | Noto Sans Devanagari (subset it — full is heavy) |
| Backend | FastAPI (Python) |
| Realtime | WebSocket for streaming inference fallback |
| DB | PostgreSQL + pgvector |
| Cache/session | Redis |
| Asset storage | Cloudflare R2 |
| Deploy | Vercel (web), Railway or Fly.io (API) |

---

## Layer 5 — Nepali Language Stack

| Task | Choice | Reality check |
|---|---|---|
| Nepali ASR | Whisper large-v3 fine-tuned on OpenSLR SLR43 + Common Voice NE | Poor out-of-box; fine-tuning is mandatory |
| Nepali TTS | `facebook/mms-tts-npi`, or VITS/Coqui fine-tuned on SLR43 | AI4Bharat Indic-TTS does **not** cover Nepali |
| Roman → Devanagari | `indic-transliteration` or small seq2seq | Critical for adoption — Nepali users type Romanized |
| Nepali NLP | Multilingual LLM, or NepBERTa for classification | |
| Date handling | `nepali-date-converter` (BS calendar) | Streaks and schedules must use Bikram Sambat |

Your Nepali speech stack will be the weakest link in the system. Always keep text input available as a fallback.

---

## Layer 6 — Tutor Logic

| Component | Choice |
|---|---|
| Spaced repetition | FSRS (`py-fsrs` / `ts-fsrs`) — better retention than SM-2 |
| Movement scoring | DTW on normalized **joint angles**, not raw coordinates |
| Feedback decomposition | Per-joint error → handshape / location / movement / orientation |

Decomposing error by sign parameter is what turns a score into teaching. "72% match" is useless; "handshape correct, movement amplitude too small" is a lesson.

---

## Layer 7 — Agents

Keep the vision model **outside** the agent loop. Agents operate on symbolic data — sign IDs, DTW scores, mastery state — never raw video. Otherwise latency destroys the experience.

| Agent | Input | Output | Language-aware? |
|---|---|---|---|
| Curriculum | mastery state, FSRS schedule | next lesson, difficulty | No |
| Critique | DTW per-joint deltas | corrective feedback text | **Yes** |
| Gloss Translation | text (ne/en) | NSL gloss + NMM tags | **Yes** |
| Animation Director | gloss sequence | clip IDs, timing, facial track | No |
| Practice Partner | scenario, learner turn | dialogue response | **Yes** |
| Data Curator | submitted clips | quality flags, dedupe | No |

**Orchestration:** LangGraph if you want the state machine provided; a plain typed orchestrator with structured outputs is simpler for six agents with mostly linear flow. Do not add a framework before you feel the pain.

**Language-aware agents need separate prompts per pair.** Nepali is SOV, English is SVO, NSL is topic-comment. One shared prompt will produce bad gloss for at least one of them.
