"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { produce, transliterate, type ProducePlan } from "@/lib/api";

const SigningAvatar = dynamic(() => import("@/components/SigningAvatar"), { ssr: false });

export default function ProducePage() {
  const t = useTranslations("produce_page");
  const locale = useLocale();
  const [text, setText] = useState(locale === "ne" ? "नमस्ते धन्यवाद" : "hello thank you");
  const [deva, setDeva] = useState("");
  const [plan, setPlan] = useState<ProducePlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onChange(v: string) {
    setText(v);
    if (locale === "ne") {
      try {
        setDeva(await transliterate(v));
      } catch {
        /* ignore preview errors */
      }
    }
  }

  async function sign() {
    setBusy(true);
    setError(null);
    try {
      setPlan(await produce(locale === "ne" && deva ? deva : text, locale));
    } catch {
      setError(t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <p className="mt-1 text-white/60">{t("subtitle")}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="flex flex-col gap-3">
          <textarea
            value={text}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-white/15 bg-white/[0.04] px-4 py-3 outline-none focus:border-[var(--accent)]"
            placeholder={t("placeholder")}
          />
          {locale === "ne" && deva && (
            <p lang="ne" className="text-sm text-white/50">
              {t("devanagari")}: <span className="text-[var(--accent)]">{deva}</span>
            </p>
          )}
          <button
            onClick={sign}
            disabled={busy || !text.trim()}
            className="w-fit rounded-lg bg-[var(--accent)] px-5 py-2.5 font-medium text-white hover:opacity-90 disabled:opacity-40"
          >
            {busy ? t("signing") : t("sign")}
          </button>

          {plan && (
            <div className="flex flex-col gap-2 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm">
              <div>
                <span className="text-white/50">{t("gloss")}:</span>{" "}
                <span className="font-mono">{plan.gloss || "—"}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {plan.steps.map((s, i) => (
                  <span key={i} className="rounded bg-white/10 px-2 py-0.5 font-mono text-xs">
                    {s.gloss}
                  </span>
                ))}
              </div>
              <div className="flex gap-4 text-xs text-white/50">
                <span>{t("duration", { ms: plan.total_ms })}</span>
                <span className={plan.has_facial_motion ? "text-emerald-300" : "text-amber-300"}>
                  {plan.has_facial_motion ? t("faceActive") : t("faceStatic")}
                </span>
              </div>
            </div>
          )}
          {error && <p className="text-amber-400">{error}</p>}
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-white/60">{t("avatarLabel")}</h2>
          <SigningAvatar plan={plan} />
          <p className="text-xs text-white/40">{t("procedural")}</p>
        </section>
      </div>
    </div>
  );
}
