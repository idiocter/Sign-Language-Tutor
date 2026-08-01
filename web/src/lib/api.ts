// Thin client for the SignBridge FastAPI backend.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export interface Sign {
  sign_id: string;
  en: string;
  ne: string;
  ne_roman: string | null;
  gloss_code: string;
  category: string | null;
  difficulty: number;
  clip_ref: string | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function listSigns(category?: string): Promise<Sign[]> {
  const q = category ? `?category=${encodeURIComponent(category)}` : "";
  return getJSON<Sign[]>(`/signs${q}`);
}

export function getSign(signId: string): Promise<Sign> {
  return getJSON<Sign>(`/signs/${signId}`);
}

export interface Prediction {
  sign_id: string;
  confidence: number;
}

export interface InferenceStatus {
  ready: boolean;
  num_classes: number;
  metrics: Record<string, unknown>;
  has_prototypes: boolean;
}

export function inferenceStatus(): Promise<InferenceStatus> {
  return getJSON<InferenceStatus>("/inference/status");
}

export function sampleFeatures(signId: string): Promise<{ sign_id: string; features: number[] }> {
  return getJSON(`/inference/sample?sign_id=${encodeURIComponent(signId)}`);
}

export async function predictFeatures(features: number[]): Promise<Prediction[]> {
  const res = await fetch(`${API_BASE}/inference/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features, top_k: 3 }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return ((await res.json()) as { predictions: Prediction[] }).predictions;
}

export async function transliterate(text: string): Promise<string> {
  const res = await fetch(`${API_BASE}/signs/transliterate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  const body = (await res.json()) as { devanagari: string };
  return body.devanagari;
}
