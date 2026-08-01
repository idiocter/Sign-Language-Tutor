// In-browser recognition with onnxruntime-web, with a graceful fallback to the backend.
//
// The plan's Phase 1 exit criterion is in-browser inference (video/features never leave
// the device). We load the interim ONNX model from /public and run it locally. If the wasm
// runtime can't initialize (e.g. blocked CDN), we fall back to the backend /inference API.

import type { Prediction } from "./api";
import { predictFeatures } from "./api";

const MODEL_URL = "/models/recognition/model.onnx";
const LABELS_URL = "/models/recognition/labels.json";

// onnxruntime-web loads its wasm assets from here. Override with NEXT_PUBLIC_ORT_WASM to
// self-host for offline use.
const ORT_WASM =
  process.env.NEXT_PUBLIC_ORT_WASM ??
  "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";

let labels: string[] = [];
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let session: any = null;
let inputName = "features";
let initTried = false;

async function tryInit(): Promise<boolean> {
  if (session) return true;
  if (initTried) return false;
  initTried = true;
  try {
    const ort = await import("onnxruntime-web");
    ort.env.wasm.wasmPaths = ORT_WASM;
    session = await ort.InferenceSession.create(MODEL_URL);
    inputName = session.inputNames?.[0] ?? "features";
    labels = (await (await fetch(LABELS_URL)).json()).labels;
    return true;
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn("onnxruntime-web unavailable, will use backend inference", e);
    session = null;
    return false;
  }
}

export interface RecognitionResult {
  predictions: Prediction[];
  engine: "browser" | "server";
}

/** Run recognition on a pooled feature vector. Prefers in-browser, falls back to server. */
export async function recognize(features: number[]): Promise<RecognitionResult> {
  if (await tryInit()) {
    const ort = await import("onnxruntime-web");
    const tensor = new ort.Tensor("float32", Float32Array.from(features), [1, features.length]);
    const out = await session.run({ [inputName]: tensor });
    const probs = out[Object.keys(out)[0]].data as Float32Array;
    const idx = Array.from(probs.keys())
      .sort((a, b) => probs[b] - probs[a])
      .slice(0, 3);
    return {
      engine: "browser",
      predictions: idx.map((i) => ({ sign_id: labels[i], confidence: probs[i] })),
    };
  }
  return { engine: "server", predictions: await predictFeatures(features) };
}
