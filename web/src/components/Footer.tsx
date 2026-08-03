import { useTranslations } from "next-intl";

export default function Footer() {
  const t = useTranslations("footer");
  return (
    <footer className="mt-16 border-t border-[var(--border)]">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-6 py-8 text-center text-xs text-white/45">
        <p>{t("tagline")}</p>
        <p>{t("builtWith")}</p>
      </div>
    </footer>
  );
}
