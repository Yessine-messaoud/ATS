import Link from "next/link";

import { cx } from "./ui";

/** Server-rendered toggle for blind screening (`?blind=1` hides candidate names). */
export function BlindToggle({ href, blind }: { href: string; blind: boolean }) {
  return (
    <Link
      href={blind ? href : `${href}?blind=1`}
      className={cx(
        "inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs",
        blind
          ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
          : "border-zinc-300 text-zinc-600 dark:border-zinc-700 dark:text-zinc-400",
      )}
      title="Hide names during screening to reduce bias"
    >
      Blind screening: {blind ? "on" : "off"}
    </Link>
  );
}

export function isBlind(value: string | string[] | undefined): boolean {
  return value === "1" || value === "true";
}
