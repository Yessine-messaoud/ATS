"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

/**
 * Feedback for AI steps that take a while (extraction runs a language model: about a minute per document on a
 * local GPU). Shows what is happening, the elapsed time and what to expect, so a long wait does not look like a hang.
 */
export function LongTask({ label, expected = "usually under a minute" }: { label: string; expected?: string }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div role="status" className="flex items-center gap-3 rounded-lg border border-brand-200 bg-brand-50/60 px-3 py-2 text-sm dark:border-brand-900 dark:bg-brand-950/40">
      <Sparkles className="size-4 shrink-0 animate-pulse text-brand-600 dark:text-brand-400" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-brand-900 dark:text-brand-200">{label}</p>
        <p className="text-xs text-brand-700/80 dark:text-brand-300/80">
          {seconds}s elapsed · {expected}. You can keep working in another tab.
        </p>
      </div>
      <div className="h-1 w-16 overflow-hidden rounded-full bg-brand-100 dark:bg-brand-900" aria-hidden>
        <div className="h-full w-1/3 animate-[slide_1.4s_ease-in-out_infinite] rounded-full bg-brand-500" />
      </div>
    </div>
  );
}
