import { Check } from "lucide-react";

import { cx } from "./ui";

const STEPS = [
  { title: "Paste & extract", detail: "AI reads the description" },
  { title: "Review & edit", detail: "Skills, experience, education" },
  { title: "Validate & publish", detail: "Becomes the scoring reference" },
];

/** Progress through job creation: 1 paste & extract (AI), 2 review & edit (recruiter), 3 validate & publish. */
export function JobSteps({ current }: { current: 1 | 2 | 3 | 4 }) {
  return (
    <ol className="grid gap-2 sm:grid-cols-3" aria-label="Job creation steps">
      {STEPS.map((step, index) => {
        const number = index + 1;
        const done = number < current;
        const active = number === current;
        return (
          <li
            key={step.title}
            aria-current={active ? "step" : undefined}
            className={cx(
              "flex items-center gap-3 rounded-lg border px-3 py-2.5",
              active ? "border-brand-300 bg-brand-50/70 dark:border-brand-800 dark:bg-brand-950/40" : "border-zinc-200 dark:border-zinc-800",
            )}
          >
            <span
              className={cx(
                "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                done ? "bg-emerald-500 text-white" : active ? "bg-brand-600 text-white" : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800",
              )}
            >
              {done ? <Check className="size-4" aria-label="done" /> : number}
            </span>
            <span className="min-w-0">
              <span className={cx("block text-sm font-medium", !active && !done && "text-zinc-500")}>{step.title}</span>
              <span className="block text-xs text-zinc-500">{step.detail}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
