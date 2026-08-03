import { setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { Badge, Button, Card } from "@/components/ui";

const FEATURES = [
  { key: "tutor", href: "/tutor", icon: "🎓" },
  { key: "practice", href: "/practice", icon: "🎥" },
  { key: "produce", href: "/produce", icon: "🧑‍🏫" },
  { key: "interpret", href: "/interpret", icon: "🔁" },
  { key: "learn", href: "/learn", icon: "📖" },
  { key: "eval", href: "/eval", icon: "📊" },
] as const;

function HomeContent() {
  const t = useTranslations("home");

  return (
    <div className="flex flex-col gap-12">
      {/* Hero */}
      <section className="flex flex-col items-start gap-5 pt-6">
        <Badge tone="accent">🇳🇵 Nepali Sign Language</Badge>
        <h1 className="max-w-3xl bg-gradient-to-br from-white to-white/60 bg-clip-text text-4xl font-bold leading-tight tracking-tight text-transparent sm:text-5xl">
          {t("title")}
        </h1>
        <p className="max-w-2xl text-lg text-white/70">{t("subtitle")}</p>
        <div className="flex flex-wrap gap-3">
          <Link href="/tutor">
            <Button size="lg">{t("startLearning")}</Button>
          </Link>
          <Link href="/produce">
            <Button size="lg" variant="secondary">
              {t("tryAvatar")}
            </Button>
          </Link>
        </div>
      </section>

      {/* Feature grid */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <Link key={f.key} href={f.href} className="group">
            <Card hover className="flex h-full flex-col gap-2 p-5">
              <span className="text-2xl">{f.icon}</span>
              <h2 className="font-semibold">{t(`features.${f.key}.title`)}</h2>
              <p className="text-sm text-white/60">{t(`features.${f.key}.body`)}</p>
              <span className="mt-auto pt-2 text-sm text-[var(--accent)] opacity-0 transition group-hover:opacity-100">
                {t("open")} →
              </span>
            </Card>
          </Link>
        ))}
      </section>

      {/* Trust row */}
      <section className="grid gap-4 sm:grid-cols-3">
        {(["privacy", "bilingual", "community"] as const).map((k) => (
          <Card key={k} className="p-5">
            <h3 className="mb-1 font-semibold">{t(`trust.${k}.title`)}</h3>
            <p className="text-sm text-white/60">{t(`trust.${k}.body`)}</p>
          </Card>
        ))}
      </section>

      <Card className="border-amber-500/30 bg-amber-500/[0.07] p-4 text-sm text-amber-200/90">
        {t("phaseNote")}
      </Card>
    </div>
  );
}

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <HomeContent />;
}
