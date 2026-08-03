"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import { listSigns, type Sign } from "@/lib/api";
import { useSession } from "@/lib/store";
import { Badge, Button, Card, Loading, PageHeader, cn } from "@/components/ui";

export default function LearnPage() {
  const t = useTranslations("learn");
  const locale = useLocale();
  const router = useRouter();
  const { setTargetSign } = useSession();
  const [signs, setSigns] = useState<Sign[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    listSigns()
      .then((d) => {
        setSigns(d);
        setStatus("ok");
      })
      .catch(() => setStatus("error"));
  }, []);

  const categories = useMemo(
    () => Array.from(new Set(signs.map((s) => s.category).filter(Boolean))) as string[],
    [signs],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return signs.filter((s) => {
      if (category && s.category !== category) return false;
      if (!q) return true;
      return (
        s.en.toLowerCase().includes(q) ||
        s.ne.includes(q) ||
        (s.ne_roman ?? "").toLowerCase().includes(q) ||
        s.sign_id.toLowerCase().includes(q)
      );
    });
  }, [signs, query, category]);

  function practice(signId: string) {
    setTargetSign(signId);
    router.push("/practice");
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("search")}
        className="w-full max-w-md rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-4 py-2 outline-none focus:border-[var(--accent)]"
      />

      {categories.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <Chip active={category === null} onClick={() => setCategory(null)}>
            {t("all")}
          </Chip>
          {categories.map((c) => (
            <Chip key={c} active={category === c} onClick={() => setCategory(c)}>
              {c}
            </Chip>
          ))}
        </div>
      )}

      {status === "loading" && <Loading label={t("loading")} />}
      {status === "error" && (
        <Card className="border-amber-500/30 bg-amber-500/[0.07] p-4 text-amber-300">{t("error")}</Card>
      )}

      {status === "ok" && (
        <>
          <p className="text-xs text-white/40">{t("count", { n: filtered.length })}</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((s) => (
              <Card key={s.sign_id} hover className="flex flex-col gap-2 p-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-lg font-semibold">{s.en}</span>
                  <span className="font-mono text-xs text-white/35">{s.sign_id}</span>
                </div>
                <p lang="ne" className="text-2xl text-[var(--accent)]">
                  {s.ne}
                </p>
                {s.ne_roman && <p className="text-sm text-white/50">{s.ne_roman}</p>}
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  {s.category && <Badge>{s.category}</Badge>}
                  <Badge tone="accent">
                    {t("difficulty")} {s.difficulty}
                  </Badge>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-2 w-full"
                  onClick={() => practice(s.sign_id)}
                >
                  {t("practiceThis")}
                </Button>
              </Card>
            ))}
            {filtered.length === 0 && (
              <Card className="col-span-full p-8 text-center text-white/50">{t("empty")}</Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-sm transition",
        active
          ? "border-[var(--accent)] bg-[var(--accent)]/15 text-[var(--accent)]"
          : "border-[var(--border)] text-white/60 hover:border-[var(--border-strong)] hover:text-white",
      )}
    >
      {children}
    </button>
  );
}
