# SignBridge — `web/`

Next.js 15 (App Router) + TypeScript + Tailwind v4 frontend. Bilingual (English / Nepali)
via `next-intl`, 3D avatar via react-three-fiber, on-device landmark detection via
MediaPipe Tasks.

## Setup

```bash
npm install
npm run dev        # http://localhost:3000  (redirects to /en)
```

The frontend talks to the API at `http://127.0.0.1:8000` by default — start the backend
(see [`../api`](../api)) so the dictionary and tutor endpoints work. Override with
`NEXT_PUBLIC_API_BASE`.

Before the webcam recognizer runs, download the MediaPipe `.task` models into
[`public/models/mediapipe/`](public/models/mediapipe/README.md).

## Structure

```
src/
  middleware.ts            next-intl locale routing (/en, /ne)
  i18n/                    routing + request config
  app/[locale]/
    layout.tsx             root document, nav, i18n provider
    page.tsx               home / dashboard
    learn/page.tsx         sign dictionary (fetches /signs)
    practice/page.tsx      avatar + webcam recognizer
  components/
    Avatar.tsx             react-three-fiber canvas (placeholder figure)
    WebcamRecognizer.tsx   MediaPipe Tasks hand landmarks, on-device
    Nav.tsx, LocaleSwitcher.tsx
  lib/
    api.ts                 backend client
    store.ts               zustand session state
    landmarks.ts           feature layout — mirrors ml/signbridge/config.py
messages/
  en.json, ne.json         translation catalogs
```

## Status (what's a stub)

- **Avatar** renders a placeholder figure. Phase 2 replaces it with authored `.glb` clips
  and co-articulation blending. The `signId` prop is the stable seam.
- **Recognition** shows detected hand landmarks only — there is no trained model yet, so no
  sign is predicted. Buffer normalized frames (`lib/landmarks.ts`) and run
  `onnxruntime-web` here once a model is exported to ONNX.
- Video is processed entirely in the browser and never uploaded.
