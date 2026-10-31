import { initials } from "@/lib/format";

import { cx } from "./ui";

const COLORS = [
  "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
  "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
  "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300",
  "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
];

/** Initials avatar; the colour comes from the record id, never from the name (no signal about the person). */
export function Avatar({ id, name, size = "md" }: { id: string; name: string | null | undefined; size?: "sm" | "md" | "lg" }) {
  const color = COLORS[parseInt(id.replace(/-/g, "").slice(0, 6), 16) % COLORS.length];
  return (
    <span
      aria-hidden
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold",
        size === "sm" ? "size-6 text-[10px]" : size === "lg" ? "size-12 text-base" : "size-8 text-xs",
        color,
      )}
    >
      {initials(name)}
    </span>
  );
}
