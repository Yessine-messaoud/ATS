"use client";

import { useState, useTransition } from "react";

import { saveWeights, type ActionState } from "@/app/actions";
import { Button, Card, Notice, inputClass } from "@/components/ui";
import type { components } from "@/lib/api-types";

type Weights = components["schemas"]["ScoringWeights"];
type Dimension = Exclude<keyof Weights, "missing_required_penalty" | "knockouts_enabled">;

const DIMENSIONS: { key: Dimension; label: string; hint: string }[] = [
  { key: "required_skills", label: "Required skills", hint: "Coverage of the required skills, weighted by how well each is demonstrated" },
  { key: "preferred_skills", label: "Preferred skills", hint: "Bonus for nice-to-have skills" },
  { key: "experience", label: "Experience", hint: "Relevant years against the stated minimum" },
  { key: "seniority", label: "Seniority", hint: "Distance between the candidate's and the role's level" },
  { key: "languages", label: "Languages", hint: "CEFR level against each requirement" },
  { key: "education", label: "Education", hint: "Kept low by default: a known source of adverse impact" },
  { key: "location", label: "Location / work mode", hint: "City, country, relocation, remote" },
];

export function WeightsForm({ jobId, initial }: { jobId: string; initial: Weights }) {
  const [weights, setWeights] = useState<Weights>(initial);
  const [state, setState] = useState<ActionState>(null);
  const [pending, startTransition] = useTransition();
  const total = DIMENSIONS.reduce((sum, d) => sum + (weights[d.key] ?? 0), 0);

  return (
    <Card title="Scoring weights">
      <p className="mb-4 text-sm text-zinc-500">
        Relative weights. They are normalized over the dimensions this job actually uses, so they need not add up to 100.
      </p>
      <div className="space-y-3">
        {DIMENSIONS.map(({ key, label, hint }) => {
          const value = weights[key] ?? 0;
          return (
            <div key={key} className="grid grid-cols-[12rem_1fr_5rem_3rem] items-center gap-3">
              <div>
                <div className="text-sm font-medium">{label}</div>
                <div className="text-xs text-zinc-500">{hint}</div>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={value}
                aria-label={label}
                onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
              />
              <input
                type="number"
                min={0}
                value={value}
                onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
                className={inputClass}
              />
              <span className="text-right text-xs tabular-nums text-zinc-500">{total ? Math.round((value / total) * 100) : 0}%</span>
            </div>
          );
        })}
        <div className="grid grid-cols-[12rem_1fr] items-center gap-3 border-t border-zinc-200 pt-3 dark:border-zinc-800">
          <div>
            <div className="text-sm font-medium">Missing required skill penalty</div>
            <div className="text-xs text-zinc-500">Score multiplied by (1 − penalty) per missing required skill</div>
          </div>
          <input
            type="number"
            min={0}
            max={0.5}
            step={0.01}
            value={weights.missing_required_penalty ?? 0.08}
            onChange={(e) => setWeights({ ...weights, missing_required_penalty: Number(e.target.value) })}
            className={`${inputClass} w-24`}
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={weights.knockouts_enabled ?? true}
            onChange={(e) => setWeights({ ...weights, knockouts_enabled: e.target.checked })}
          />
          Apply mandatory criteria (knock-outs)
        </label>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button disabled={pending || total === 0} onClick={() => startTransition(async () => setState(await saveWeights(jobId, weights)))}>
          {pending ? "Saving…" : "Save weights"}
        </Button>
        {total === 0 && <Notice tone="red">At least one weight must be positive.</Notice>}
        {state?.error && <Notice tone="red">{state.error}</Notice>}
        {state?.ok && <Notice tone="green">{state.ok}</Notice>}
      </div>
    </Card>
  );
}
