import type { Metadata } from "next";
import { EyeOff, Gavel, MessageSquare, ShieldCheck, Sparkles } from "lucide-react";

import { startConversation } from "@/app/actions";
import { Button, Card, PageHeader, cx, focusRing } from "@/components/ui";

export const metadata: Metadata = { title: "Assistant" };

const EXAMPLES = [
  "Who are the top 3 candidates for the Data Engineer job, and why?",
  "Is there a better opportunity than the Data Engineer job for Youssef Trabelsi?",
  "Prepare interview questions for Amira Gharbi for the Data Engineer role.",
  "Rédige un email de refus bienveillant pour Karim Mansour pour le stage PFE.",
];

const PROMISES = [
  { icon: Gavel, text: "Scores come from the same engine as the ranking pages, never from the AI." },
  { icon: ShieldCheck, text: "Nothing changes without your confirmation; every action is audited." },
  { icon: EyeOff, text: "Requests to filter on protected characteristics are refused." },
];

export default function AssistantPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Recruitment assistant"
        description="Ask in plain language, in English or French: rank, compare, explain a score, prepare an interview, draft an email or update a pipeline."
      />

      <Card>
        <form action={startConversation} className="space-y-3">
          <label htmlFor="prompt" className="sr-only">
            Your question
          </label>
          <textarea
            id="prompt"
            name="prompt"
            rows={3}
            placeholder="Ask anything about your jobs and candidates…"
            className="w-full resize-none rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-zinc-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-zinc-700 dark:bg-zinc-950"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <input type="checkbox" name="blind" className="size-4 rounded border-zinc-300 accent-brand-600" />
              Blind screening (hide candidate names)
            </label>
            <Button type="submit" icon={<MessageSquare className="size-4" />}>
              Start
            </Button>
          </div>
        </form>
      </Card>

      <div>
        <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-500">
          <Sparkles className="size-3.5" aria-hidden /> Try
        </h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {EXAMPLES.map((example) => (
            <form key={example} action={startConversation}>
              <input type="hidden" name="prompt" value={example} />
              <button
                type="submit"
                className={cx(
                  "h-full w-full rounded-xl border border-zinc-200 bg-white p-3 text-left text-sm shadow-sm transition hover:border-brand-300 hover:bg-brand-50/40 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-brand-700",
                  focusRing,
                )}
              >
                {example}
              </button>
            </form>
          ))}
        </div>
      </div>

      <ul className="grid gap-3 sm:grid-cols-3">
        {PROMISES.map(({ icon: Icon, text }) => (
          <li key={text} className="flex items-start gap-2 text-xs text-zinc-500">
            <Icon className="mt-0.5 size-4 shrink-0 text-brand-500" aria-hidden />
            {text}
          </li>
        ))}
      </ul>
    </div>
  );
}
