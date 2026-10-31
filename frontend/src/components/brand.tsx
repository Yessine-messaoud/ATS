import Link from "next/link";

import { cx, focusRing } from "./ui";

/** The RecruitAI logo. `light` sits on the navy sidebar; `dark` adapts to the page background. */
export function BrandMark({ href = "/", tone = "light" }: { href?: string; tone?: "light" | "dark" }) {
  return (
    <Link href={href} className={cx("relative flex items-center gap-2.5 rounded-md", focusRing)}>
      <span className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-lavender-600 shadow-sm">
        <svg viewBox="0 0 24 24" className="size-4 text-white" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
          <path d="M5 19 12 5l7 14M8.5 13h7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className={cx("text-[15px] font-semibold tracking-tight", tone === "light" ? "text-white" : "text-zinc-900 dark:text-white")}>
        Recruit<span className={tone === "light" ? "text-brand-300" : "text-brand-600 dark:text-brand-300"}>AI</span>
      </span>
    </Link>
  );
}
