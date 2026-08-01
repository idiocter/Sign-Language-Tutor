"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { listSigns, type Sign } from "@/lib/api";

export default function LearnPage() {
  const t = useTranslations("learn");
  const [signs, setSigns] = useState<Sign[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    listSigns()
      .then((data) => {
        setSigns(data);
        setStatus("ok");
      })
      .catch(() => setStatus("error"));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return signs;
    return signs.filter(
      (s) =>
        s.en.toLowerCase().includes(q) ||
        s.ne.includes(q) ||
        (s.ne_roman ?? "").toLowerCase().includes(q) ||
        s.sign_id.toLowerCase().includes(q),
    );
  }, [signs, query]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("search")}
        className="w-full max-w-md rounded-lg border border-white/15 bg-white/[0.04] px-4 py-2 outline-none focus:border-[var(--accent)]"
      />

      {status === "loading" && <p className="text-white/60">{t("loading")}</p>}
      {status === "error" && <p className="text-amber-400">{t("error")}</p>}

      {status === "ok" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((s) => (
            <div
              key={s.sign_id}
              className="rounded-xl border border-white/10 bg-white/[0.03] p-4"
            >
              <div className="flex items-baseline justify-between">
                <span className="text-lg font-semibold">{s.en}</span>
                <span className="font-mono text-xs text-white/40">{s.sign_id}</span>
              </div>
              <p lang="ne" className="text-xl text-[var(--accent)]">
                {s.ne}
              </p>
              {s.ne_roman && <p className="text-sm text-white/50">{s.ne_roman}</p>}
              <div className="mt-2 flex gap-3 text-xs text-white/50">
                {s.category && <span>{s.category}</span>}
                <span>
                  {t("difficulty")}: {s.difficulty}
                </span>
              </div>
            </div>
          ))}
          {filtered.length === 0 && <p className="text-white/60">{t("empty")}</p>}
        </div>
      )}
    </div>
  );
}
