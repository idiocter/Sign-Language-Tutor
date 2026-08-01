"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  createLearner,
  getLearner,
  getLearnerLesson,
  listSigns,
  produceSign,
  submitReview,
  type LearnerState,
  type ProducePlan,
  type Sign,
} from "@/lib/api";

const SigningAvatar = dynamic(() => import("@/components/SigningAvatar"), { ssr: false });

const LS_KEY = "signbridge_learner_id";
const RATINGS = [
  { rating: 1, key: "again", cls: "bg-red-500/20 text-red-200 hover:bg-red-500/30" },
  { rating: 2, key: "hard", cls: "bg-amber-500/20 text-amber-200 hover:bg-amber-500/30" },
  { rating: 3, key: "good", cls: "bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30" },
  { rating: 4, key: "easy", cls: "bg-sky-500/20 text-sky-200 hover:bg-sky-500/30" },
] as const;

export default function TutorPage() {
  const t = useTranslations("tutor");
  const locale = useLocale();
  const [learner, setLearner] = useState<LearnerState | null>(null);
  const [signsById, setSignsById] = useState<Record<string, Sign>>({});
  const [queue, setQueue] = useState<string[]>([]);
  const [idx, setIdx] = useState(0);
  const [plan, setPlan] = useState<ProducePlan | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Bootstrap: load or create a learner + the sign dictionary.
  useEffect(() => {
    (async () => {
      try {
        const all = await listSigns();
        setSignsById(Object.fromEntries(all.map((s) => [s.sign_id, s])));
        const stored = typeof window !== "undefined" ? window.localStorage.getItem(LS_KEY) : null;
        let state: LearnerState;
        if (stored) {
          try {
            state = await getLearner(Number(stored));
          } catch {
            state = await createLearner(locale);
          }
        } else {
          state = await createLearner(locale);
        }
        window.localStorage.setItem(LS_KEY, String(state.id));
        setLearner(state);
      } catch {
        setError(t("error"));
      }
    })();
  }, [locale, t]);

  const startLesson = useCallback(async () => {
    if (!learner) return;
    setError(null);
    setDone(false);
    try {
      const lesson = await getLearnerLesson(learner.id, 8);
      const q = [...lesson.review, ...lesson.new];
      setQueue(q);
      setIdx(0);
      if (q.length === 0) setDone(true);
    } catch {
      setError(t("error"));
    }
  }, [learner, t]);

  // Load the avatar plan for the current card.
  useEffect(() => {
    const signId = queue[idx];
    if (!signId) return;
    setPlan(null);
    produceSign(signId).then(setPlan).catch(() => setPlan(null));
  }, [queue, idx]);

  async function rate(rating: number) {
    const signId = queue[idx];
    if (!learner || !signId) return;
    try {
      await submitReview(learner.id, signId, rating);
    } catch {
      /* keep going; review is best-effort */
    }
    if (idx + 1 < queue.length) {
      setIdx(idx + 1);
    } else {
      setDone(true);
      getLearner(learner.id).then(setLearner).catch(() => {});
    }
  }

  const current = queue[idx];
  const sign = current ? signsById[current] : undefined;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-white/60">{t("subtitle")}</p>
        </div>
        {learner && (
          <div className="flex gap-4 text-sm">
            <Stat label={t("streak")} value={`${learner.streak} 🔥`} />
            <Stat label={t("mastered")} value={`${learner.signs_mastered}`} />
            <Stat label={t("due")} value={`${learner.due_count}`} />
          </div>
        )}
      </div>
      {learner && <p className="text-xs text-white/40">{t("todayBs", { date: learner.today_bs })}</p>}

      {error && <p className="text-amber-400">{error}</p>}

      {/* idle / summary */}
      {(queue.length === 0 || done) && (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-6">
          <p className="text-white/70">{done && queue.length ? t("sessionDone") : t("ready")}</p>
          <button
            onClick={startLesson}
            className="rounded-lg bg-[var(--accent)] px-5 py-2.5 font-medium text-white hover:opacity-90"
          >
            {done && queue.length ? t("again2") : t("start")}
          </button>
        </div>
      )}

      {/* active card */}
      {queue.length > 0 && !done && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs text-white/50">
              <span>
                {t("card", { n: idx + 1, total: queue.length })}
              </span>
              <span className="font-mono">{current}</span>
            </div>
            <div className="h-1 w-full overflow-hidden rounded bg-white/10">
              <div
                className="h-full bg-[var(--accent)] transition-all"
                style={{ width: `${((idx + 1) / queue.length) * 100}%` }}
              />
            </div>
            <SigningAvatar plan={plan} />
          </section>

          <section className="flex flex-col justify-center gap-4">
            {sign && (
              <div className="text-center">
                <p className="text-3xl font-bold">{sign.en}</p>
                <p lang="ne" className="text-2xl text-[var(--accent)]">
                  {sign.ne}
                </p>
                {sign.ne_roman && <p className="text-white/50">{sign.ne_roman}</p>}
              </div>
            )}
            <p className="text-center text-sm text-white/50">{t("rate")}</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {RATINGS.map((r) => (
                <button
                  key={r.rating}
                  onClick={() => rate(r.rating)}
                  className={`rounded-lg px-3 py-3 text-sm font-medium transition ${r.cls}`}
                >
                  {t(`ratings.${r.key}`)}
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-center">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-white/50">{label}</div>
    </div>
  );
}
