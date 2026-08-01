import { setRequestLocale } from "next-intl/server";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";

function HomeContent() {
  const t = useTranslations("home");
  const cards = [
    { key: "recognize", body: "recognizeBody" },
    { key: "avatar", body: "avatarBody" },
    { key: "tutor", body: "tutorBody" },
  ] as const;

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-4">
        <h1 className="text-4xl font-bold tracking-tight">{t("title")}</h1>
        <p className="max-w-2xl text-lg text-white/70">{t("subtitle")}</p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/practice"
            className="rounded-lg bg-[var(--accent)] px-5 py-2.5 font-medium text-white hover:opacity-90"
          >
            {t("startPractice")}
          </Link>
          <Link
            href="/learn"
            className="rounded-lg border border-white/15 px-5 py-2.5 font-medium hover:bg-white/5"
          >
            {t("browseDictionary")}
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {cards.map(({ key, body }) => (
          <div key={key} className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
            <h2 className="mb-2 font-semibold">{t(`cards.${key}`)}</h2>
            <p className="text-sm text-white/60">{t(`cards.${body}`)}</p>
          </div>
        ))}
      </section>

      <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200/90">
        {t("phaseNote")}
      </p>
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
