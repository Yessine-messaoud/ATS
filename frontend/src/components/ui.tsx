import type { ComponentProps, ReactNode } from "react";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

const BUTTON_VARIANTS = {
  primary: "bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300",
  secondary:
    "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800",
  ghost: "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
  danger: "bg-red-600 text-white hover:bg-red-500",
};

export function Button({
  variant = "primary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: keyof typeof BUTTON_VARIANTS }) {
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

const TONES = {
  neutral: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  green: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20 dark:bg-emerald-950 dark:text-emerald-300",
  amber: "bg-amber-50 text-amber-800 ring-1 ring-amber-600/20 dark:bg-amber-950 dark:text-amber-300",
  red: "bg-red-50 text-red-700 ring-1 ring-red-600/20 dark:bg-red-950 dark:text-red-300",
  blue: "bg-sky-50 text-sky-700 ring-1 ring-sky-600/20 dark:bg-sky-950 dark:text-sky-300",
};
export type Tone = keyof typeof TONES;

export function Badge({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={cx("inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium", TONES[tone])}>
      {children}
    </span>
  );
}

export const STATUS_TONE: Record<string, Tone> = {
  met: "green",
  pass: "green",
  partial: "amber",
  unknown: "amber",
  missing: "red",
  fail: "red",
  unverified: "red",
};

export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
          <h2 className="text-sm font-semibold">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const percent = Math.max(0, Math.min(100, (score / max) * 100));
  const color = percent >= 75 ? "bg-emerald-500" : percent >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800" aria-hidden>
        <div className={cx("h-full rounded-full", color)} style={{ width: `${percent}%` }} />
      </div>
      <span className="w-10 text-right text-sm tabular-nums">{max === 100 ? score.toFixed(1) : `${Math.round(percent)}%`}</span>
    </div>
  );
}

export function Notice({ tone = "amber", children }: { tone?: Tone; children: ReactNode }) {
  return <div className={cx("rounded-md px-3 py-2 text-sm", TONES[tone])}>{children}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-zinc-500">{children}</p>;
}

export const inputClass =
  "w-full rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-950 focus:outline-none focus:ring-2 focus:ring-zinc-400";
