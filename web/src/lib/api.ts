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
  location_label?: string;
  movement_label?: string;
  handshape: string;
  curl: number;
  /** Per-finger flexion [thumb, index, middle, ring, pinky], 0=extended..1=folded. */
  fingers?: [number, number, number, number, number];
  spread?: number;
  thumb_out?: number;
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

export interface LearnerState {
  id: number;
  display_name: string;
  language: string;
  mastery: Record<string, number>;
  signs_started: number;
  signs_mastered: number;
  due_count: number;
  streak: number;
  today_bs: string;
}

export interface Lesson {
  review: string[];
  new: string[];
  difficulty: number;
}

export async function createLearner(language: string): Promise<LearnerState> {
  const res = await fetch(`${API_BASE}/tutor/learner`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: "Learner", language }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<LearnerState>;
}

export function getLearner(id: number): Promise<LearnerState> {
  return getJSON<LearnerState>(`/tutor/learner/${id}`);
}

export function getLearnerLesson(id: number, size = 8): Promise<Lesson> {
  return getJSON<Lesson>(`/tutor/learner/${id}/lesson?size=${size}`);
}

export async function submitReview(id: number, signId: string, rating: number): Promise<void> {
  const res = await fetch(`${API_BASE}/tutor/learner/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sign_id: signId, rating }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
}

export function produceSign(signId: string): Promise<ProducePlan> {
  return getJSON<ProducePlan>(`/produce/sign?sign_id=${encodeURIComponent(signId)}`);
}

export interface SignToText {
  gloss: string;
  text: string;
  text_en: string;
  text_ne: string;
  unknown: string[];
}

export async function signToText(signIds: string[], language: string): Promise<SignToText> {
  const res = await fetch(`${API_BASE}/interpret/sign-to-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sign_ids: signIds, language }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<SignToText>;
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

export interface EvalModels {
  recognition: Record<string, unknown> | null;
  fingerspelling: Record<string, unknown> | null;
}

export interface RatingsSummary {
  count: number;
  mean_score: number | null;
  passes_gate: boolean;
  per_sign: { sign_id: string; count: number; mean: number }[];
}

export function getEvalModels(): Promise<EvalModels> {
  return getJSON<EvalModels>("/eval/models");
}

export function getRatingsSummary(): Promise<RatingsSummary> {
  return getJSON<RatingsSummary>("/eval/ratings/summary");
}

export async function submitRating(signId: string, score: number, comment?: string): Promise<void> {
  const res = await fetch(`${API_BASE}/eval/rating`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sign_id: signId, score, comment }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
}

export interface Score {
  overall: number;
  parameters: Record<string, number>;
  feedback_target: string;
  feedback_message: string;
  passed: boolean;
}

export async function scoreDemo(signId: string, language: string, noise = 0.12): Promise<Score> {
  const q = new URLSearchParams({ sign_id: signId, language, noise: String(noise) });
  const res = await fetch(`${API_BASE}/tutor/score-demo?${q}`, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<Score>;
}

export async function scoreSign(signId: string, learner: number[][], language: string): Promise<Score> {
  const res = await fetch(`${API_BASE}/tutor/score-sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sign_id: signId, learner, language }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<Score>;
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
