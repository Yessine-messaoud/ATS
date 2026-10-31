"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardCheck, KanbanSquare, ListOrdered, SlidersHorizontal } from "lucide-react";

import { cx, focusRing } from "@/components/ui";

const TABS = [
  { segment: "", label: "Ranking", icon: ListOrdered },
  { segment: "/requirements", label: "Requirements", icon: ClipboardCheck },
  { segment: "/pipeline", label: "Pipeline", icon: KanbanSquare },
  { segment: "/weights", label: "Weights", icon: SlidersHorizontal },
];

export function JobTabs({ jobId, needsValidation }: { jobId: string; needsValidation: boolean }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Job sections" className="-mx-4 overflow-x-auto border-b border-zinc-200 px-4 dark:border-zinc-800 sm:mx-0 sm:px-0">
      <div className="flex gap-1">
        {TABS.map(({ segment, label, icon: Icon }) => {
          const href = `/jobs/${jobId}${segment}`;
          const active = pathname === href;
          return (
            <Link
              key={label}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cx(
                "-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm",
                active
                  ? "border-indigo-600 font-medium text-indigo-700 dark:border-indigo-400 dark:text-indigo-300"
                  : "border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100",
                focusRing,
              )}
            >
              <Icon className="size-4" aria-hidden />
              {label}
              {segment === "/requirements" && needsValidation && (
                <span className="size-1.5 rounded-full bg-amber-500" aria-label="needs validation" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
