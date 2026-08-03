// Small, dependency-free UI kit shared across pages for a consistent look.
// Server-safe (no hooks) so it can be used in server or client components.

import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

// --- Button -----------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANT: Record<Variant, string> = {
  primary:
    "bg-[var(--accent)] text-white hover:brightness-110 shadow-lg shadow-[var(--accent)]/20",
  secondary: "border border-[var(--border-strong)] text-white hover:bg-[var(--surface-hover)]",
  ghost: "text-white/75 hover:text-white hover:bg-[var(--surface)]",
  danger: "bg-red-500/85 text-white hover:bg-red-500",
};
const SIZE: Record<Size, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition",
        "disabled:cursor-not-allowed disabled:opacity-40",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...props}
    />
  );
}

// --- Card -------------------------------------------------------------------

export function Card({
  children,
  className,
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] backdrop-blur-sm",
        hover && "transition hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

// --- Badge ------------------------------------------------------------------

type Tone = "neutral" | "accent" | "success" | "warning" | "danger";
const TONE: Record<Tone, string> = {
  neutral: "bg-white/10 text-white/70",
  accent: "bg-[var(--accent)]/15 text-[var(--accent)]",
  success: "bg-emerald-500/15 text-emerald-300",
  warning: "bg-amber-500/15 text-amber-300",
  danger: "bg-red-500/15 text-red-300",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

// --- Spinner ----------------------------------------------------------------

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="loading"
      className={cn(
        "inline-block h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-[var(--accent)]",
        className,
      )}
    />
  );
}

export function Loading({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-8 text-sm text-white/60">
      <Spinner /> {label ?? "Loading…"}
    </div>
  );
}

// --- Page header ------------------------------------------------------------

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-white/60">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

// --- Stat -------------------------------------------------------------------

export function Stat({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <Card className="px-3 py-2 text-center">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-white/50">{label}</div>
    </Card>
  );
}
