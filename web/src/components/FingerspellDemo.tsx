"use client";

// Phase 1.5 fingerspelling demo. Type a word -> transliterate to Devanagari -> fingerspell
// each character -> recognize each handshape (interim model on synthetic hand poses).

import { useState } from "react";
import { useTranslations } from "next-intl";
import { fingerspell, type SpellResult } from "@/lib/api";

export default function FingerspellDemo() {
  const t = useTranslations("fingerspell");
  const [word, setWord] = useState("namaste");
  const [result, setResult] = useState<SpellResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await fingerspell(word));
    } catch {
      setError(t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <h3 className="text-sm font-medium text-white/70">{t("title")}</h3>
      <div className="flex gap-2">
        <input
          value={word}
          onChange={(e) => setWord(e.target.value)}
          placeholder={t("placeholder")}
          className="flex-1 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
        />
        <button
          onClick={run}
          disabled={busy || !word.trim()}
          className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          {busy ? t("spelling") : t("spell")}
        </button>
      </div>

      {result && (
        <div className="flex flex-col gap-2">
          <p lang="ne" className="text-2xl text-[var(--accent)]">
            {result.devanagari}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {result.chars.map((c, i) => (
              <span
                key={i}
                title={`${c.target_roman} → ${(c.confidence * 100).toFixed(0)}%`}
                className={`rounded px-2 py-1 text-lg ${
                  c.correct
                    ? "bg-emerald-500/15 text-emerald-200"
                    : "bg-red-500/15 text-red-200"
                }`}
                lang="ne"
              >
                {c.target_char}
              </span>
            ))}
          </div>
          <p className="text-xs text-white/50">
            {t("recognized", { pct: Math.round(result.accuracy * 100) })}
          </p>
        </div>
      )}
      {error && <p className="text-sm text-amber-400">{error}</p>}
      <p className="text-xs text-white/40">{t("synthetic")}</p>
    </div>
  );
}
