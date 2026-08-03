"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { produce, transliterate, type ProducePlan } from "@/lib/api";
import { Badge, Button, Card, PageHeader } from "@/components/ui";

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
      <PageHeader title={t("title")} subtitle={t("subtitle")} />

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="flex flex-col gap-3">
          <textarea
            value={text}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-4 py-3 outline-none focus:border-[var(--accent)]"
            placeholder={t("placeholder")}
          />
          {locale === "ne" && deva && (
            <p lang="ne" className="text-sm text-white/50">
              {t("devanagari")}: <span className="text-[var(--accent)]">{deva}</span>
            </p>
          )}
          <Button onClick={sign} disabled={busy || !text.trim()} className="w-fit" size="lg">
            {busy ? t("signing") : t("sign")}
          </Button>

          {plan && (
            <Card className="flex flex-col gap-2 p-3 text-sm">
              <div>
                <span className="text-white/50">{t("gloss")}:</span>{" "}
                <span className="font-mono">{plan.gloss || "—"}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {plan.steps.map((s, i) => (
                  <Badge key={i} tone="neutral" className="font-mono">
                    {s.gloss}
                  </Badge>
                ))}
              </div>
              <div className="flex gap-4 text-xs text-white/50">
                <span>{t("duration", { ms: plan.total_ms })}</span>
                <span className={plan.has_facial_motion ? "text-emerald-300" : "text-amber-300"}>
                  {plan.has_facial_motion ? t("faceActive") : t("faceStatic")}
                </span>
              </div>
            </Card>
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
