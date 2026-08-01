import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import LocaleSwitcher from "./LocaleSwitcher";

export default function Nav() {
  const t = useTranslations("nav");
  const tApp = useTranslations("app");

  return (
    <header className="flex items-center justify-between border-b border-white/10 px-6 py-4">
      <Link href="/" className="text-lg font-semibold tracking-tight">
        {tApp("name")}
      </Link>
      <nav className="flex items-center gap-6 text-sm">
        <Link href="/" className="text-white/80 hover:text-white">
          {t("home")}
        </Link>
        <Link href="/tutor" className="text-white/80 hover:text-white">
          {t("tutor")}
        </Link>
        <Link href="/learn" className="text-white/80 hover:text-white">
          {t("learn")}
        </Link>
        <Link href="/practice" className="text-white/80 hover:text-white">
          {t("practice")}
        </Link>
        <Link href="/produce" className="text-white/80 hover:text-white">
          {t("produce")}
        </Link>
        <LocaleSwitcher />
      </nav>
    </header>
  );
}
