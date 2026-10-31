"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { CalendarRange } from "lucide-react";

import { Button, cx, focusRing, inputClass } from "@/components/ui";

const PRESETS = [
  { key: "7", label: "Last 7 days" },
  { key: "30", label: "Last 30 days" },
  { key: "90", label: "Last 90 days" },
  { key: "custom", label: "Custom" },
];

/** Date-range filter kept in the URL (?range=7|30|90|custom&from=&to=), so views are shareable and server-rendered. */
export function RangeFilter({ current, from, to }: { current: string; from: string; to: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [custom, setCustom] = useState(current === "custom");
  const [start, setStart] = useState(from);
  const [end, setEnd] = useState(to);

  const go = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null) next.delete(key);
      else next.set(key, value);
    }
    router.push(`${pathname}?${next}`, { scroll: false });
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div role="radiogroup" aria-label="Date range" className="flex rounded-lg border border-zinc-200 bg-white p-0.5 dark:border-zinc-800 dark:bg-zinc-900">
        {PRESETS.map((preset) => {
          const active = preset.key === "custom" ? custom : !custom && current === preset.key;
          return (
            <button
              key={preset.key}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => {
                if (preset.key === "custom") setCustom(true);
                else {
                  setCustom(false);
                  go({ range: preset.key, from: null, to: null });
                }
              }}
              className={cx(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                active ? "bg-brand-600 text-white shadow-sm" : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100",
                focusRing,
              )}
            >
              {preset.label}
            </button>
          );
        })}
      </div>
      {custom && (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            go({ range: "custom", from: start, to: end });
          }}
        >
          <CalendarRange className="size-4 text-zinc-400" aria-hidden />
          <input type="date" aria-label="From" value={start} max={end} onChange={(e) => setStart(e.target.value)} className={cx(inputClass, "w-auto")} required />
          <span className="text-xs text-zinc-500">to</span>
          <input type="date" aria-label="To" value={end} min={start} onChange={(e) => setEnd(e.target.value)} className={cx(inputClass, "w-auto")} required />
          <Button type="submit" size="sm">
            Apply
          </Button>
        </form>
      )}
    </div>
  );
}
