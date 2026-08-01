"use client";

// Phase 1 recognition demo. Fetches a synthesized attempt for the target sign from the
// backend, then recognizes it — preferring in-browser onnxruntime-web, falling back to the
// server. Proves the train -> export -> infer loop end-to-end without a webcam or model
// downloads. The model is the interim classifier trained on synthetic data.

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { inferenceStatus, sampleFeatures, type InferenceStatus, type Prediction } from "@/lib/api";
import { recognize } from "@/lib/recognition";

export default function RecognitionDemo({ signId }: { signId: string }) {
  const t = useTranslations("recognize");
  const [status, setStatus] = useState<InferenceStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{
    predictions: Prediction[];
    engine: string;
    correct: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    inferenceStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  async function run() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const { features } = await sampleFeatures(signId);
      const { predictions, engine } = await recognize(features);
      setResult({
        predictions,
        engine,
        correct: predictions[0]?.sign_id === signId,
      });
    } catch {
      setError(t("error"));
    } finally {
      setBusy(false);
    }
  }

  const acc = status?.metrics?.["test_accuracy_heldout_signers"] as number | undefined;

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-white/70">{t("title")}</h3>
        {status && (
          <span
            className={`rounded px-2 py-0.5 text-xs ${
              status.ready ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
            }`}
          >
            {status.ready ? t("ready", { n: status.num_classes }) : t("noModel")}
          </span>
        )}
      </div>

      {status?.ready && acc !== undefined && (
        <p className="text-xs text-white/50">{t("selfTest", { acc: Math.round(acc * 100) })}</p>
      )}

      <button
        onClick={run}
        disabled={busy || !status?.ready}
        className="w-fit rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
      >
        {busy ? t("running") : t("test")}
      </button>

      {result && (
        <div className="flex flex-col gap-1 text-sm">
          <div className="flex items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                result.correct ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"
              }`}
            >
              {result.correct ? t("correct") : t("wrong")}
            </span>
            <span className="text-xs text-white/40">
              {t("engine")}: {result.engine}
            </span>
          </div>
          <ul className="text-white/70">
            {result.predictions.map((p, i) => (
              <li key={p.sign_id} className={i === 0 ? "font-medium" : "text-white/50"}>
                {p.sign_id} — {(p.confidence * 100).toFixed(1)}%
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="text-sm text-amber-400">{error}</p>}
      <p className="text-xs text-white/40">{t("synthetic")}</p>
    </div>
  );
}
