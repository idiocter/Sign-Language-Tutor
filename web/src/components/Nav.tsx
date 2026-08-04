"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/routing";
import { routing } from "@/i18n/routing";
import LocaleSwitcher from "./LocaleSwitcher";
import { cn } from "./ui";

const LINKS: { href: string; key: string; icon: string }[] = [
  { href: "/", key: "home", icon: "🏠" },
  { href: "/tutor", key: "tutor", icon: "🎓" },
  { href: "/learn", key: "learn", icon: "📖" },
  { href: "/practice", key: "practice", icon: "🎥" },
  { href: "/produce", key: "produce", icon: "🧑‍🏫" },
  { href: "/interpret", key: "interpret", icon: "🔁" },
  { href: "/eval", key: "eval", icon: "📊" },
];

export default function Nav() {
  const t = useTranslations("nav");
  const tApp = useTranslations("app");
  const rawPath = usePathname();
  const locale = useLocale();
  const [open, setOpen] = useState(false);

  // Be robust whether usePathname returns "/tutor" or "/en/tutor".
  let path = rawPath || "/";
  for (const l of routing.locales) {
    if (path === `/${l}`) path = "/";
    else if (path.startsWith(`/${l}/`)) path = path.slice(l.length + 1);
  }
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2 text-lg font-semibold tracking-tight">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--accent-2)] text-sm">
            🤟
          </span>
          <span className="hidden sm:inline">{tApp("name")}</span>
        </Link>

        {/* Desktop links — visible from md up, scroll if narrow. */}
        <nav className="hidden flex-1 items-center gap-0.5 overflow-x-auto md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={isActive(l.href) ? "page" : undefined}
              className={cn(
                "whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm transition",
                isActive(l.href)
                  ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                  : "text-white/70 hover:bg-[var(--surface)] hover:text-white",
              )}
            >
              {t(l.key)}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <div className="hidden sm:block">
            <LocaleSwitcher />
          </div>
          <button
            type="button"
            aria-label="Toggle menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="grid h-9 w-9 place-items-center rounded-lg border border-[var(--border-strong)] text-white/80 md:hidden"
          >
            <span className="relative block h-4 w-5">
              <span className={cn("absolute left-0 top-0 h-0.5 w-5 bg-current transition-all", open && "top-1.5 rotate-45")} />
              <span className={cn("absolute left-0 top-1.5 h-0.5 w-5 bg-current transition-all", open && "opacity-0")} />
              <span className={cn("absolute left-0 top-3 h-0.5 w-5 bg-current transition-all", open && "top-1.5 -rotate-45")} />
            </span>
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {open && (
        <nav className="border-t border-[var(--border)] px-3 py-3 md:hidden">
          <div className="grid grid-cols-2 gap-1.5">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                aria-current={isActive(l.href) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition",
                  isActive(l.href)
                    ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                    : "bg-[var(--surface)] text-white/80 hover:bg-[var(--surface-hover)]",
                )}
              >
                <span>{l.icon}</span>
                {t(l.key)}
              </Link>
            ))}
          </div>
          <div className="mt-3 sm:hidden">
            <LocaleSwitcher />
          </div>
        </nav>
      )}
    </header>
  );
}
