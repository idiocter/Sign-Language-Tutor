# SignBridge — What to Download

Verify URLs before use — model paths and dataset hosting change. Version numbers in MediaPipe paths in particular get bumped.

---

## 1. MediaPipe Task Models

Download these three `.task` files into `models/mediapipe/`.

```bash
mkdir -p models/mediapipe && cd models/mediapipe

# Hand landmarker — 21 points per hand
wget https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

# Pose landmarker — 33 body points
wget https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker.task

# Face landmarker — 478 points + blendshape output
wget https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
```

The face landmarker also outputs **ARKit blendshape coefficients directly** — this is what connects your recognition side to your avatar's facial rig. Same 52-parameter space on both ends.

---

## 2. Sign Language Datasets (pretraining)

| Dataset | Content | Where |
|---|---|---|
| **WLASL** | ~2,000 ASL glosses, 21k videos | `github.com/dxli94/WLASL` |
| **MS-ASL** | 1,000 ASL classes | Microsoft Research download page |
| **AUTSL** | Turkish SL, 226 signs, clean recordings | `cvml.ankara.edu.tr` |
| **INCLUDE** | Indian SL, 263 signs | Zenodo — closest regional neighbour to NSL |

Start with **WLASL** for pretraining. Skeleton features transfer across sign languages far better than raw pixels do.

**NSL data does not exist publicly. You will collect it.** That is the real work of Phase 0–1.

---

## 3. Nepali Speech Data & Models

```bash
# ASR fine-tuning data
# OpenSLR SLR43 — Nepali speech corpus
wget https://www.openslr.org/resources/43/ne_np_female.zip

# Pre-cleaned combined set (SLR43 + Common Voice), ~3000 samples
# HuggingFace: amitpant7/nepali-speech-to-text
```

```python
# Nepali TTS — Meta MMS
from transformers import VitsModel, AutoTokenizer
model = VitsModel.from_pretrained("facebook/mms-tts-npi")
tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-npi")

# ASR base to fine-tune
# openai/whisper-large-v3   (or whisper-small if VRAM-limited)
```

Note: AI4Bharat's Indic-TTS covers 13 Indic languages but **not Nepali**. Don't waste time looking for it there.

---

## 4. Avatar Assets

| Asset | Source | Cost |
|---|---|---|
| Rigged humanoid character | Mixamo (`mixamo.com`) | Free, Adobe account |
| Alternative avatar | Ready Player Me | Free tier |
| Blender 4.x | `blender.org/download` | Free |
| ARKit blendshape reference | Apple ARKit docs — `ARFaceAnchor.BlendShapeLocation` | Free |
| VRM support (optional) | `github.com/pixiv/three-vrm` | Free |

**Check your character has facial blendshapes before you commit to it.** Many free rigs are body-only. Retargeting a face rig later is painful.

---

## 5. Python Environment

```bash
pip install -r requirements.txt
```

See `requirements.txt` in this folder.

---

## 6. Node / Frontend

```bash
npx create-next-app@latest signbridge-web --typescript --tailwind --app

cd signbridge-web
npm install three @react-three/fiber @react-three/drei
npm install @mediapipe/tasks-vision onnxruntime-web
npm install zustand next-intl ts-fsrs
npm install nepali-date-converter
```

---

## 7. Fonts

- **Noto Sans Devanagari** — `fonts.google.com/noto/specimen/Noto+Sans+Devanagari`
- Subset it with `glyphhanger` or `pyftsubset`. The full font is several hundred KB and you only need a fraction of the glyph coverage.

---

## 8. Reference Reading

Worth the time before you start modelling:

- **HamNoSys** notation — the standard for transcribing sign phonology. Even if you use a simplified scheme, read this first so your schema isn't naive.
- **Progressive Transformers for End-to-End SLP** (Saunders et al.) — read it to understand *why* you're choosing clip-based synthesis instead.
- **Sign Language Production: A Review** (Rastgoo et al.) — the honest survey of what does and doesn't work.
- Nepal National Federation of the Deaf and Hard of Hearing — for NSL resources and community contact.
