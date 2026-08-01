"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  getEvalModels,
  getRatingsSummary,
  listSigns,
  produceSign,
  submitRating,
  type EvalModels,
  type ProducePlan,
  type RatingsSummary,
  type Sign,
} from "@/lib/api";

const SigningAvatar = dynamic(() => import("@/components/SigningAvatar"), { ssr: false });

function pct(v: unknown): string {
  return typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
}

export default function EvalPage() {
  const t = useTranslations("eval");
  const [models, setModels] = useState<EvalModels | null>(null);
  const [summary, setSummary] = useState<RatingsSummary | null>(null);
  const [signs, setSigns] = useState<Sign[]>([]);
  const [signId, setSignId] = useState("NSL_0001");
  const [plan, setPlan] = useState<ProducePlan | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getEvalModels().then(setModels).catch(() => setModels(null));
    getRatingsSummary().then(setSummary).catch(() => setSummary(null));
    listSigns().then(setSigns).catch(() => setSigns([]));
  }, []);

  useEffect(() => {
    produceSign(signId).then(setPlan).catch(() => setPlan(null));
  }, [signId]);

  async function rate(score: number) {
    await submitRating(signId, score).catch(() => {});
    setSaved(true);
    getRatingsSummary().then(setSummary).catch(() => {});
    setTimeout(() => setSaved(false), 1500);
  }

  const rec = models?.recognition as Record<string, unknown> | null;
  const fs = models?.fingerspelling as Record<string, unknown> | null;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-white/60">{t("subtitle")}</p>
      </div>

      <section className="grid gap-4 sm:grid-cols-2">
        <MetricCard
          title={t("recognition")}
          rows={[
            [t("heldoutAcc"), pct(rec?.["test_accuracy_heldout_signers"])],
            [t("classes"), String(rec?.["num_classes"] ?? "—")],
            [t("data"), rec?.["synthetic"] ? t("synthetic") : t("real")],
          ]}
        />
        <MetricCard
          title={t("fingerspelling")}
          rows={[
            [t("heldoutAcc"), pct(fs?.["test_accuracy_heldout_signers"])],
            [t("classes"), String(fs?.["num_classes"] ?? "—")],
            [t("data"), fs?.["synthetic"] ? t("synthetic") : t("real")],
          ]}
        />
      </section>

      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-xl font-semibold">{t("intelTitle")}</h2>
          <p className="text-sm text-white/60">{t("intelSubtitle")}</p>
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="flex flex-col gap-3">
            <select
              value={signId}
              onChange={(e) => setSignId(e.target.value)}
              className="w-fit rounded-lg border border-white/15 bg-white/[0.04] px-3 py-1.5"
            >
              {signs.map((s) => (
                <option key={s.sign_id} value={s.sign_id}>
                  {s.en} — {s.ne}
                </option>
              ))}
            </select>
            <SigningAvatar plan={plan} />
          </div>
          <div className="flex flex-col justify-center gap-3">
            <p className="text-sm text-white/60">{t("ratePrompt")}</p>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  onClick={() => rate(n)}
                  className="h-11 w-11 rounded-lg border border-white/15 text-lg hover:border-[var(--accent)] hover:bg-white/5"
                >
                  {n}
                </button>
              ))}
            </div>
            {saved && <p className="text-sm text-emerald-300">{t("saved")}</p>}
            {summary && (
              <div className="mt-2 rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm">
                <p>
                  {t("mean")}:{" "}
                  <span className={summary.passes_gate ? "text-emerald-300" : "text-amber-300"}>
                    {summary.mean_score ?? "—"} / 5
                  </span>{" "}
                  <span className="text-white/40">({summary.count})</span>
                </p>
                <p className="mt-1 text-xs text-white/50">
                  {summary.passes_gate ? t("gatePass") : t("gateFail")}
                </p>
              </div>
            )}
          </div>
        </div>
      </section>

      <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200/90">
        {t("note")}
      </p>
    </div>
  );
}

function MetricCard({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
      <h3 className="mb-3 font-semibold">{title}</h3>
      <dl className="flex flex-col gap-1.5 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between">
            <dt className="text-white/50">{k}</dt>
            <dd className="font-medium">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
