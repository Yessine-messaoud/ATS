import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { ChevronRight, Loader2 } from "lucide-react";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

/** Keyboard focus ring shared by every interactive element. */
export const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-zinc-950";

const BUTTON_VARIANTS = {
  primary: "bg-indigo-600 text-white shadow-sm hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400",
  secondary:
    "border border-zinc-300 bg-white text-zinc-900 shadow-sm hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800",
  ghost: "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
  danger: "bg-red-600 text-white shadow-sm hover:bg-red-500",
};
const BUTTON_SIZES = { sm: "h-7 px-2 text-xs", md: "h-9 px-3 text-sm" };

type ButtonProps = ComponentProps<"button"> & {
  variant?: keyof typeof BUTTON_VARIANTS;
  size?: keyof typeof BUTTON_SIZES;
  loading?: boolean;
  icon?: ReactNode;
};

export function buttonClass(variant: keyof typeof BUTTON_VARIANTS = "primary", size: keyof typeof BUTTON_SIZES = "md") {
  return cx(
    "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
    BUTTON_SIZES[size],
    BUTTON_VARIANTS[variant],
    focusRing,
  );
}

export function Button({ variant = "primary", size = "md", loading, icon, className, children, disabled, ...props }: ButtonProps) {
  return (
    <button className={cx(buttonClass(variant, size), className)} disabled={disabled || loading} {...props}>
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

/** A link styled as a button. */
export function ButtonLink({
  variant = "secondary",
  size = "md",
  icon,
  className,
  children,
  ...props
}: ComponentProps<typeof Link> & { variant?: keyof typeof BUTTON_VARIANTS; size?: keyof typeof BUTTON_SIZES; icon?: ReactNode }) {
  return (
    <Link className={cx(buttonClass(variant, size), className)} {...props}>
      {icon}
      {children}
    </Link>
  );
}

const TONES = {
  neutral: "bg-zinc-100 text-zinc-700 ring-1 ring-zinc-500/10 dark:bg-zinc-800 dark:text-zinc-300",
  green: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20 dark:bg-emerald-950 dark:text-emerald-300",
  amber: "bg-amber-50 text-amber-800 ring-1 ring-amber-600/20 dark:bg-amber-950 dark:text-amber-300",
  red: "bg-red-50 text-red-700 ring-1 ring-red-600/20 dark:bg-red-950 dark:text-red-300",
  blue: "bg-sky-50 text-sky-700 ring-1 ring-sky-600/20 dark:bg-sky-950 dark:text-sky-300",
  indigo: "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/20 dark:bg-indigo-950 dark:text-indigo-300",
};
export type Tone = keyof typeof TONES;

export function Badge({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs font-medium", TONES[tone])}
    >
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

export function Card({
  title,
  description,
  actions,
  children,
  className,
  flush,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** No inner padding (tables and lists that run edge to edge). */
  flush?: boolean;
}) {
  return (
    <section
      className={cx(
        "rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">{title}</h2>
            {description && <p className="mt-0.5 text-xs text-zinc-500">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}

export function scoreTone(percent: number): string {
  return percent >= 75 ? "bg-emerald-500" : percent >= 50 ? "bg-amber-500" : "bg-red-500";
}

export function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const percent = Math.max(0, Math.min(100, (score / max) * 100));
  return (
    <div className="flex items-center gap-2" title={`${percent.toFixed(0)}%`}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800" aria-hidden>
        <div className={cx("h-full rounded-full", scoreTone(percent))} style={{ width: `${percent}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-medium tabular-nums">
        {max === 100 ? score.toFixed(1) : `${Math.round(percent)}%`}
      </span>
    </div>
  );
}

/** Circular score gauge for headers. */
export function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const percent = Math.max(0, Math.min(100, score));
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const color = percent >= 75 ? "text-emerald-500" : percent >= 50 ? "text-amber-500" : "text-red-500";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`Score ${score.toFixed(1)} out of 100`}>
      <svg viewBox="0 0 64 64" className="size-full -rotate-90">
        <circle cx="32" cy="32" r={radius} className="fill-none stroke-zinc-200 dark:stroke-zinc-800" strokeWidth="6" />
        <circle
          cx="32"
          cy="32"
          r={radius}
          className={cx("fill-none stroke-current", color)}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - percent / 100)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold tabular-nums">
        {score.toFixed(0)}
      </span>
    </div>
  );
}

export function Notice({ tone = "amber", icon, children }: { tone?: Tone; icon?: ReactNode; children: ReactNode }) {
  return (
    <div className={cx("flex items-start gap-2 rounded-lg px-3 py-2 text-sm", TONES[tone])}>
      {icon && <span className="mt-0.5 shrink-0 [&>svg]:size-4">{icon}</span>}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function Empty({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
      {icon && <div className="rounded-full bg-zinc-100 p-3 text-zinc-500 dark:bg-zinc-800 [&>svg]:size-5">{icon}</div>}
      {title && <p className="text-sm font-medium">{title}</p>}
      {children && <div className="max-w-sm text-sm text-zinc-500">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon,
  href,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  href?: string;
}) {
  const body = (
    <>
      <div className="flex items-center justify-between text-xs font-medium text-zinc-500">
        {label}
        {icon && <span className="text-zinc-400 [&>svg]:size-4">{icon}</span>}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-zinc-500">{hint}</div>}
    </>
  );
  const className =
    "block rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900";
  return href ? (
    <Link href={href} className={cx(className, "transition-colors hover:border-indigo-300 dark:hover:border-indigo-700", focusRing)}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

export type Crumb = { label: string; href?: string };

export function PageHeader({
  crumbs,
  title,
  badges,
  description,
  actions,
}: {
  crumbs?: Crumb[];
  title: ReactNode;
  badges?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        {crumbs && crumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="mb-1 flex flex-wrap items-center gap-1 text-xs text-zinc-500">
            {crumbs.map((crumb, index) => (
              <span key={`${crumb.label}-${index}`} className="flex items-center gap-1">
                {index > 0 && <ChevronRight className="size-3" aria-hidden />}
                {crumb.href ? (
                  <Link href={crumb.href} className={cx("rounded hover:text-zinc-900 dark:hover:text-zinc-100", focusRing)}>
                    {crumb.label}
                  </Link>
                ) : (
                  <span>{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}
        <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
          {title}
          {badges}
        </h1>
        {description && <p className="mt-1 text-sm text-zinc-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-md bg-zinc-200/80 dark:bg-zinc-800", className)} aria-hidden />;
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-zinc-300 bg-zinc-50 px-1 font-mono text-[10px] text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800">
      {children}
    </kbd>
  );
}

export const inputClass = cx(
  "w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-sm shadow-sm placeholder:text-zinc-400 dark:border-zinc-700 dark:bg-zinc-950",
  "focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30",
);

export const tableClass = "w-full text-sm";
export const theadClass =
  "border-b border-zinc-200 bg-zinc-50 text-left text-xs font-medium text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60";
