"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { listSigns, produceSign, type ProducePlan, type Sign } from "@/lib/api";
import { useSession } from "@/lib/store";
import WebcamRecognizer from "@/components/WebcamRecognizer";
import RecognitionDemo from "@/components/RecognitionDemo";
import FingerspellDemo from "@/components/FingerspellDemo";
import ScoreFeedback from "@/components/ScoreFeedback";

// three.js must not render on the server.
const SigningAvatar = dynamic(() => import("@/components/SigningAvatar"), { ssr: false });

export default function PracticePage() {
  const t = useTranslations("practice");
  const { targetSignId, setTargetSign } = useSession();
  const [signs, setSigns] = useState<Sign[]>([]);
  const [plan, setPlan] = useState<ProducePlan | null>(null);

  useEffect(() => {
    listSigns().then(setSigns).catch(() => setSigns([]));
  }, []);

  useEffect(() => {
    produceSign(targetSignId).then(setPlan).catch(() => setPlan(null));
  }, [targetSignId]);

  const target = signs.find((s) => s.sign_id === targetSignId);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
        <label className="flex items-center gap-2 text-sm text-white/70">
          {t("targetSign")}
          <select
            value={targetSignId}
            onChange={(e) => setTargetSign(e.target.value)}
            className="rounded-lg border border-white/15 bg-white/[0.04] px-3 py-1.5 outline-none"
          >
            {signs.map((s) => (
              <option key={s.sign_id} value={s.sign_id}>
                {s.en} — {s.ne}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-white/60">{t("avatarLabel")}</h2>
          <SigningAvatar plan={plan} />
          {target && (
            <p lang="ne" className="text-center text-xl text-[var(--accent)]">
              {target.ne} <span className="text-white/50">/ {target.en}</span>
            </p>
          )}
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-white/60">{t("recognizerLabel")}</h2>
          <WebcamRecognizer />
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <RecognitionDemo signId={targetSignId} />
        <ScoreFeedback signId={targetSignId} />
      </div>

      <FingerspellDemo />
    </div>
  );
}
