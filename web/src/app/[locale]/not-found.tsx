import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";

export default function NotFound() {
  const t = useTranslations("nav");
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <h1 className="text-5xl font-bold">404</h1>
      <Link href="/" className="text-[var(--accent)] hover:underline">
        {t("home")}
      </Link>
    </div>
  );
}
