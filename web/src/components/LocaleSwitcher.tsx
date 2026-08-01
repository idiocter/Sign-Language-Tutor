"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/routing";
import { routing } from "@/i18n/routing";

export default function LocaleSwitcher() {
  const locale = useLocale();
  const t = useTranslations("language");
  const router = useRouter();
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-1 rounded-lg border border-white/10 p-1">
      {routing.locales.map((loc) => (
        <button
          key={loc}
          onClick={() => router.replace(pathname, { locale: loc })}
          aria-current={loc === locale}
          className={`rounded-md px-2 py-1 text-sm transition ${
            loc === locale ? "bg-[var(--accent)] text-white" : "text-white/70 hover:text-white"
          }`}
        >
          {t(loc)}
        </button>
      ))}
    </div>
  );
}
