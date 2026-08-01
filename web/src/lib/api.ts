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
