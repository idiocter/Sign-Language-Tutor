"use client";

// Phase 3 movement scoring. Runs the real DTW-on-joint-angles algorithm against the sign's
// reference and shows the per-parameter error decomposition + the Critique agent's
// localized, joint-level feedback. Uses a synthesized attempt (score-demo) so it works
// without a webcam; the same endpoint (score-sign) scores real captured frames.

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { scoreDemo, type Score } from "@/lib/api";

const PARAMS = ["handshape", "location", "movement", "orientation"] as const;

export default function ScoreFeedback({ signId }: { signId: string }) {
  const t = useTranslations("score");
  const locale = useLocale();
  const [score, setScore] = useState<Score | null>(null);
  const [busy, setBusy] = useState(false);
  const [quality, setQuality] = useState(0.12); // demo attempt noise

  async function run() {
    setBusy(true);
    try {
      setScore(await scoreDemo(signId, locale, quality));
    } catch {
      setScore(null);
    } finally {
      setBusy(false);
    }
  }

  // Normalize raw DTW errors to 0..1 bars for display (higher error = fuller/redder bar).
  const maxErr = score ? Math.max(...PARAMS.map((p) => score.parameters[p] ?? 0), 0.001) : 1;

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <h3 className="text-sm font-medium text-white/70">{t("title")}</h3>

      <label className="flex items-center gap-2 text-xs text-white/50">
        {t("attempt")}
        <input
          type="range"
          min={0.02}
          max={0.6}
          step={0.02}
          value={quality}
          onChange={(e) => setQuality(Number(e.target.value))}
          className="flex-1 accent-[var(--accent)]"
        />
        <span>{quality < 0.15 ? t("clean") : quality < 0.35 ? t("okay") : t("sloppy")}</span>
      </label>

      <button
        onClick={run}
        disabled={busy}
        className="w-fit rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
      >
        {busy ? t("scoring") : t("score")}
      </button>

      {score && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold">{score.overall.toFixed(0)}</span>
            <span
              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                score.passed ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
              }`}
            >
              {score.passed ? t("passed") : t("keepGoing")}
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            {PARAMS.map((p) => {
              const err = score.parameters[p] ?? 0;
              const frac = Math.min(err / maxErr, 1);
              const worst = p === score.feedback_target;
              return (
                <div key={p} className="flex items-center gap-2 text-xs">
                  <span className={`w-24 ${worst ? "text-amber-300" : "text-white/60"}`}>{t(`params.${p}`)}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded bg-white/10">
                    <div
                      className={`h-full ${worst ? "bg-amber-400" : "bg-emerald-400/70"}`}
                      style={{ width: `${(1 - frac) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="rounded-lg bg-white/[0.04] px-3 py-2 text-sm" lang={locale}>
            {score.feedback_message}
          </p>
        </div>
      )}
      <p className="text-xs text-white/40">{t("note")}</p>
    </div>
  );
}
