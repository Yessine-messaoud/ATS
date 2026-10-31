"use client";

import Link from "next/link";
import { useOptimistic, useState, useTransition } from "react";
import { GripVertical } from "lucide-react";

import { moveApplication } from "@/app/actions";
import { Avatar } from "@/components/avatar";
import { useToast } from "@/components/toaster";
import { cx, focusRing } from "@/components/ui";
import type { components } from "@/lib/api-types";
import { STAGES, STAGE_LABELS } from "@/lib/enums";

type Application = components["schemas"]["ApplicationOut"];
type Stage = Application["stage"];

// Active stages are columns; closed outcomes sit below as wide drop zones, so names are not truncated.
const ACTIVE: Stage[] = ["new", "screening", "interview", "offer", "hired"];
const CLOSED: Stage[] = ["rejected", "withdrawn"];

const STAGE_DOT: Record<Stage, string> = {
  new: "bg-zinc-400",
  screening: "bg-sky-500",
  interview: "bg-brand-500",
  offer: "bg-violet-500",
  hired: "bg-emerald-500",
  rejected: "bg-red-400",
  withdrawn: "bg-zinc-300",
};

export function Kanban({ applications, blind }: { applications: Application[]; blind: boolean }) {
  const [optimistic, applyMove] = useOptimistic(applications, (current, move: { id: string; stage: Stage }) =>
    current.map((a) => (a.id === move.id ? { ...a, stage: move.stage } : a)),
  );
  const [, startTransition] = useTransition();
  const [dragOver, setDragOver] = useState<Stage | null>(null);
  const notify = useToast();

  const move = (id: string, stage: Stage) => {
    const application = optimistic.find((a) => a.id === id);
    if (!application || application.stage === stage) return;
    startTransition(async () => {
      applyMove({ id, stage });
      const result = await moveApplication(id, stage);
      if (result?.error) notify(result.error, "error");
      else notify(`${application.display_name} moved to ${STAGE_LABELS[stage]}.`);
    });
  };

  const column = (stage: Stage, closed = false) => {
    const cards = optimistic.filter((a) => a.stage === stage);
    return (
      <section
        key={stage}
        aria-label={STAGE_LABELS[stage]}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(stage);
        }}
        onDragLeave={() => setDragOver(null)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(null);
          move(e.dataTransfer.getData("text/plain"), stage);
        }}
        className={cx(
          "rounded-xl border-2 bg-zinc-100/70 p-2 transition-colors dark:bg-zinc-900/60",
          closed ? "min-h-24" : "min-h-56",
          dragOver === stage ? "border-brand-400 bg-brand-50/60 dark:bg-brand-950/30" : "border-transparent",
        )}
      >
        <h3 className="mb-2 flex items-center justify-between px-1 text-xs font-semibold text-zinc-600 dark:text-zinc-300">
          <span className="flex items-center gap-1.5">
            <span className={cx("size-2 rounded-full", STAGE_DOT[stage])} aria-hidden />
            {STAGE_LABELS[stage]}
          </span>
          <span className="rounded-full bg-white px-1.5 tabular-nums text-zinc-500 dark:bg-zinc-800">{cards.length}</span>
        </h3>
        <div className={closed ? "grid gap-2 sm:grid-cols-2 xl:grid-cols-3" : "space-y-2"}>
          {cards.length === 0 && (
            <p className="rounded-lg border border-dashed border-zinc-300 px-2 py-3 text-center text-[11px] text-zinc-400 dark:border-zinc-700">
              Drop here
            </p>
          )}
          {cards.map((application) => (
            <article
              key={application.id}
              draggable
              onDragStart={(e) => e.dataTransfer.setData("text/plain", application.id)}
              className="group cursor-grab rounded-lg border border-zinc-200 bg-white p-2.5 text-sm shadow-sm transition hover:shadow-md active:cursor-grabbing dark:border-zinc-700 dark:bg-zinc-800"
            >
              <div className="flex items-start gap-2">
                {!blind && <Avatar id={application.candidate_id} name={application.display_name} size="sm" />}
                <div className="min-w-0 flex-1">
                  {blind ? (
                    <span className="block truncate font-medium">{application.display_name}</span>
                  ) : (
                    <Link
                      href={`/candidates/${application.candidate_id}`}
                      className={cx("block truncate rounded font-medium hover:underline", focusRing)}
                      title={application.display_name}
                    >
                      {application.display_name}
                    </Link>
                  )}
                  <div className="mt-0.5 text-xs tabular-nums text-zinc-500">score {application.overall_score?.toFixed(1) ?? "—"}</div>
                </div>
                <GripVertical className="size-4 shrink-0 text-zinc-300 group-hover:text-zinc-500" aria-hidden />
              </div>
              {application.passed_knockouts === false && (
                <p className="mt-1.5 rounded bg-red-50 px-1.5 py-0.5 text-[11px] font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
                  mandatory criterion not met
                </p>
              )}
              <select
                aria-label={`Move ${application.display_name} to stage`}
                value={application.stage}
                onChange={(e) => move(application.id, e.target.value as Stage)}
                className="mt-2 w-full rounded-md border border-zinc-200 bg-zinc-50 px-1.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/40 dark:border-zinc-700 dark:bg-zinc-900"
              >
                {STAGES.map((option) => (
                  <option key={option} value={option}>
                    {STAGE_LABELS[option]}
                  </option>
                ))}
              </select>
            </article>
          ))}
        </div>
      </section>
    );
  };

  return (
    <div className="space-y-3">
      <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
        <div className="grid min-w-[52rem] grid-cols-5 gap-3">{ACTIVE.map((stage) => column(stage))}</div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">{CLOSED.map((stage) => column(stage, true))}</div>
    </div>
  );
}
