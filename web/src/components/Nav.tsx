"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/routing";
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
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--bg)]/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--accent-2)] text-sm">
            🤟
          </span>
          {tApp("name")}
        </Link>

        {/* desktop links */}
        <nav className="hidden items-center gap-1 lg:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm transition",
                isActive(l.href)
                  ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                  : "text-white/70 hover:bg-[var(--surface)] hover:text-white",
              )}
            >
              {t(l.key)}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <div className="hidden sm:block">
            <LocaleSwitcher />
          </div>
          {/* mobile menu button */}
          <button
            aria-label="Menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="rounded-lg border border-[var(--border-strong)] p-2 text-white/80 lg:hidden"
          >
            <span className="block h-4 w-5">
              <span className={cn("block h-0.5 w-5 bg-current transition", open && "translate-y-1.5 rotate-45")} />
              <span className={cn("mt-1 block h-0.5 w-5 bg-current transition", open && "opacity-0")} />
              <span className={cn("mt-1 block h-0.5 w-5 bg-current transition", open && "-translate-y-1.5 -rotate-45")} />
            </span>
          </button>
        </div>
      </div>

      {/* mobile drawer */}
      {open && (
        <nav className="flex flex-col gap-1 border-t border-[var(--border)] px-4 py-3 lg:hidden">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                isActive(l.href)
                  ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                  : "text-white/75 hover:bg-[var(--surface)]",
              )}
            >
              <span>{l.icon}</span>
              {t(l.key)}
            </Link>
          ))}
          <div className="mt-2 sm:hidden">
            <LocaleSwitcher />
          </div>
        </nav>
      )}
    </header>
  );
}
