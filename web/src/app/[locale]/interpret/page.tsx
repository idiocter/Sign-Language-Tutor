"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  listSigns,
  produce,
  signToText,
  type ProducePlan,
  type Sign,
} from "@/lib/api";
import { listenOnce, speak, speechSupported } from "@/lib/speech";
import { PageHeader } from "@/components/ui";

const SigningAvatar = dynamic(() => import("@/components/SigningAvatar"), { ssr: false });

type Direction = "text2sign" | "sign2text";

export default function InterpretPage() {
  const t = useTranslations("interpret");
  const locale = useLocale();
  const [dir, setDir] = useState<Direction>("text2sign");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />

      <div className="flex w-fit gap-1 rounded-lg border border-[var(--border)] p-1">
        {(["text2sign", "sign2text"] as Direction[]).map((d) => (
          <button
            key={d}
            onClick={() => setDir(d)}
            className={`rounded-md px-4 py-1.5 text-sm transition ${
              dir === d ? "bg-[var(--accent)] text-white" : "text-white/70 hover:text-white"
            }`}
          >
            {t(d)}
          </button>
        ))}
      </div>

      {dir === "text2sign" ? <TextToSign locale={locale} /> : <SignToText locale={locale} />}

      <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200/90">
        {t("scopeNote")}
      </p>
    </div>
  );
}

function TextToSign({ locale }: { locale: string }) {
  const t = useTranslations("interpret");
  const [text, setText] = useState(locale === "ne" ? "नमस्ते" : "hello");
  const [plan, setPlan] = useState<ProducePlan | null>(null);
  const [listening, setListening] = useState(false);

  async function mic() {
    setListening(true);
    try {
      setText(await listenOnce(locale));
    } catch {
      /* fall back to typing */
    } finally {
      setListening(false);
    }
  }

  async function go() {
    try {
      setPlan(await produce(text, locale));
    } catch {
      setPlan(null);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="flex flex-col gap-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-white/15 bg-white/[0.04] px-4 py-3 outline-none focus:border-[var(--accent)]"
        />
        <div className="flex gap-2">
          <button
            onClick={go}
            className="rounded-lg bg-[var(--accent)] px-5 py-2.5 font-medium text-white hover:opacity-90"
          >
            {t("toSign")}
          </button>
          {speechSupported() && (
            <button
              onClick={mic}
              className="rounded-lg border border-white/15 px-4 py-2.5 hover:bg-white/5"
            >
              {listening ? t("listening") : `🎤 ${t("speak")}`}
            </button>
          )}
        </div>
        {plan && <p className="font-mono text-sm text-white/60">{plan.gloss}</p>}
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium text-white/60">{t("avatarLabel")}</h2>
        <SigningAvatar plan={plan} />
      </section>
    </div>
  );
}

function SignToText({ locale }: { locale: string }) {
  const t = useTranslations("interpret");
  const [signs, setSigns] = useState<Sign[]>([]);
  const [seq, setSeq] = useState<Sign[]>([]);
  const [out, setOut] = useState<{ text: string; gloss: string } | null>(null);

  useEffect(() => {
    listSigns().then(setSigns).catch(() => setSigns([]));
  }, []);

  async function interpret() {
    if (seq.length === 0) return;
    try {
      const r = await signToText(seq.map((s) => s.sign_id), locale);
      setOut({ text: r.text, gloss: r.gloss });
    } catch {
      setOut(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-white/50">{t("pickHint")}</p>
      {/* recognized-sign sequence */}
      <div className="flex min-h-[3rem] flex-wrap gap-2 rounded-lg border border-white/10 bg-white/[0.03] p-3">
        {seq.length === 0 && <span className="text-white/30">{t("empty")}</span>}
        {seq.map((s, i) => (
          <span key={i} className="rounded bg-[var(--accent)]/20 px-2 py-1 text-sm text-[var(--accent)]">
            {locale === "ne" ? s.ne : s.en}
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <button
          onClick={interpret}
          disabled={seq.length === 0}
          className="rounded-lg bg-[var(--accent)] px-5 py-2 font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          {t("toText")}
        </button>
        <button onClick={() => { setSeq([]); setOut(null); }} className="rounded-lg border border-white/15 px-4 py-2 hover:bg-white/5">
          {t("clear")}
        </button>
      </div>

      {out && (
        <div className="flex flex-col gap-2 rounded-lg border border-white/10 bg-white/[0.03] p-4">
          <p className="text-lg" lang={locale}>{out.text || "—"}</p>
          <p className="font-mono text-xs text-white/50">{out.gloss}</p>
          <button
            onClick={() => speak(out.text, locale)}
            className="w-fit rounded-lg border border-white/15 px-3 py-1.5 text-sm hover:bg-white/5"
          >
            🔊 {t("speakText")}
          </button>
        </div>
      )}

      {/* sign palette (stands in for continuous recognition) */}
      <div className="flex flex-wrap gap-1.5">
        {signs.slice(0, 30).map((s) => (
          <button
            key={s.sign_id}
            onClick={() => setSeq((q) => [...q, s])}
            className="rounded border border-white/10 px-2 py-1 text-xs text-white/70 hover:border-[var(--accent)] hover:text-white"
          >
            {locale === "ne" ? s.ne : s.en}
          </button>
        ))}
      </div>
    </div>
  );
}
