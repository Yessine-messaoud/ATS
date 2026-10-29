"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cx } from "@/components/ui";

const TABS = [
  { segment: "", label: "Ranking" },
  { segment: "/requirements", label: "Requirements" },
  { segment: "/pipeline", label: "Pipeline" },
  { segment: "/weights", label: "Weights" },
];

export function JobTabs({ jobId }: { jobId: string }) {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 border-b border-zinc-200 dark:border-zinc-800">
      {TABS.map(({ segment, label }) => {
        const href = `/jobs/${jobId}${segment}`;
        const active = pathname === href;
        return (
          <Link
            key={label}
            href={href}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-sm",
              active
                ? "border-zinc-900 font-medium dark:border-zinc-100"
                : "border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100",
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
