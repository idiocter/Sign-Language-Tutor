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

export interface HandPose {
  location: [number, number, number];
  handshape: string;
  curl: number;
  palm_normal: [number, number, number];
}

export interface Pose {
  two_handed: boolean;
  symmetric: boolean;
  movement: { kind: string; amplitude: number; repeats: number };
  right_hand: HandPose;
  left_hand: HandPose | null;
  procedural: boolean;
}

export interface FacialTrack {
  blendshapes: Record<string, number>;
  head_rotation: [number, number, number];
  head_gesture: "nod" | "shake" | null;
  static: boolean;
}

export interface AnimationStep {
  sign_id: string;
  gloss: string;
  clip_ref: string | null;
  start_ms: number;
  duration_ms: number;
  crossfade_ms: number;
  pose: Pose | null;
  facial: FacialTrack;
}

export interface ProducePlan {
  gloss: string;
  sentence_nmm: Record<string, string>;
  total_ms: number;
  has_facial_motion: boolean;
  steps: AnimationStep[];
}

export async function produce(text: string, language: string): Promise<ProducePlan> {
  const res = await fetch(`${API_BASE}/produce`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<ProducePlan>;
}

export interface SpellChar {
  target_char: string;
  target_roman: string;
  predicted_char: string;
  correct: boolean;
  confidence: number;
}

export interface SpellResult {
  input: string;
  devanagari: string;
  chars: SpellChar[];
  accuracy: number;
}

export function fingerspell(word: string): Promise<SpellResult> {
  return getJSON<SpellResult>(`/inference/fingerspell/spell?word=${encodeURIComponent(word)}`);
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
