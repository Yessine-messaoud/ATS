"use client";

import Link from "next/link";
import { useOptimistic, useState, useTransition } from "react";

import { moveApplication } from "@/app/actions";
import { Notice, cx, inputClass } from "@/components/ui";
import type { components } from "@/lib/api-types";
import { STAGES, STAGE_LABELS } from "@/lib/enums";

type Application = components["schemas"]["ApplicationOut"];
type Stage = Application["stage"];

export function Kanban({ applications, blind }: { applications: Application[]; blind: boolean }) {
  const [optimistic, applyMove] = useOptimistic(applications, (current, move: { id: string; stage: Stage }) =>
    current.map((a) => (a.id === move.id ? { ...a, stage: move.stage } : a)),
  );
  const [, startTransition] = useTransition();
  const [dragOver, setDragOver] = useState<Stage | null>(null);
  const [error, setError] = useState<string>();

  const move = (id: string, stage: Stage) => {
    if (optimistic.find((a) => a.id === id)?.stage === stage) return;
    startTransition(async () => {
      applyMove({ id, stage });
      const result = await moveApplication(id, stage);
      setError(result?.error);
    });
  };

  return (
    <div className="space-y-3">
      {error && <Notice tone="red">{error}</Notice>}
      <div className="grid gap-3 overflow-x-auto md:grid-cols-4 xl:grid-cols-7">
        {STAGES.map((stage) => {
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
                "min-h-40 rounded-lg border bg-zinc-100/60 p-2 dark:bg-zinc-900/60",
                dragOver === stage ? "border-zinc-500" : "border-transparent",
              )}
            >
              <h3 className="mb-2 flex justify-between px-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                {STAGE_LABELS[stage]}
                <span>{cards.length}</span>
              </h3>
              <div className="space-y-2">
                {cards.map((application) => (
                  <article
                    key={application.id}
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData("text/plain", application.id)}
                    className="cursor-grab rounded-md border border-zinc-200 bg-white p-2 text-sm shadow-sm active:cursor-grabbing dark:border-zinc-700 dark:bg-zinc-800"
                  >
                    <div className="font-medium">
                      {blind ? (
                        application.display_name
                      ) : (
                        <Link href={`/candidates/${application.candidate_id}`} className="hover:underline">
                          {application.display_name}
                        </Link>
                      )}
                    </div>
                    <div className="mt-1 flex items-center justify-between text-xs text-zinc-500">
                      <span className="tabular-nums">score {application.overall_score?.toFixed(1) ?? "—"}</span>
                      {application.passed_knockouts === false && <span className="text-red-600">criterion not met</span>}
                    </div>
                    <select
                      aria-label="Move to stage"
                      value={application.stage}
                      onChange={(e) => move(application.id, e.target.value as Stage)}
                      className={cx(inputClass, "mt-2 py-0.5 text-xs")}
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
        })}
      </div>
    </div>
  );
}
