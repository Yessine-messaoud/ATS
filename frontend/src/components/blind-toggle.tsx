import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";

import { cx, focusRing } from "./ui";

/** Server-rendered switch for blind screening (`?blind=1` hides candidate names). */
export function BlindToggle({ href, blind }: { href: string; blind: boolean }) {
  return (
    <Link
      href={blind ? href : `${href}?blind=1`}
      role="switch"
      aria-checked={blind}
      className={cx(
        "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
        blind
          ? "border-brand-600 bg-brand-600 text-white dark:border-brand-400 dark:bg-brand-500"
          : "border-zinc-300 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800",
        focusRing,
      )}
      title="Hide names during screening to reduce bias"
    >
      {blind ? <EyeOff className="size-3.5" aria-hidden /> : <Eye className="size-3.5" aria-hidden />}
      Blind screening {blind ? "on" : "off"}
    </Link>
  );
}

export function isBlind(value: string | string[] | undefined): boolean {
  return value === "1" || value === "true";
}
