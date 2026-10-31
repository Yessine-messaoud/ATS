"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Gavel, Plus } from "lucide-react";

import { addToPipeline, moveApplication } from "@/app/actions";
import { useToast } from "@/components/toaster";
import { Button, Field, inputClass, selectClass } from "@/components/ui";
import type { Stage } from "@/lib/api";
import { STAGES, STAGE_LABELS } from "@/lib/enums";

/**
 * Recruiter decision controls: the only place where a decision is recorded. The AI never changes a stage;
 * every decision here is written to the audit log with the recruiter's note.
 */
export function DecisionPanel({
  jobId,
  candidateId,
  application,
}: {
  jobId: string;
  candidateId: string;
  application: { id: string; stage: Stage } | null;
}) {
  const [stage, setStage] = useState<Stage>(application?.stage ?? "screening");
  const [note, setNote] = useState("");
  const [pending, startTransition] = useTransition();
  const notify = useToast();
  const router = useRouter();

  if (!application) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-zinc-500">This candidate is not in the job&apos;s pipeline yet.</p>
        <Button
          loading={pending}
          icon={<Plus className="size-4" />}
          onClick={() =>
            startTransition(async () => {
              const result = await addToPipeline(jobId, candidateId);
              if (result?.error) notify(result.error, "error");
              else {
                notify(result?.ok ?? "Added to the pipeline.");
                router.refresh();
              }
            })
          }
        >
          Add to pipeline
        </Button>
      </div>
    );
  }

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        startTransition(async () => {
          const result = await moveApplication(application.id, stage, note);
          if (result?.error) notify(result.error, "error");
          else {
            notify(`Decision recorded: ${STAGE_LABELS[stage]}.`);
            setNote("");
          }
        });
      }}
    >
      <Field label="Pipeline stage">
        <select value={stage} onChange={(e) => setStage(e.target.value as Stage)} className={selectClass}>
          {STAGES.map((option) => (
            <option key={option} value={option}>
              {STAGE_LABELS[option]}
              {option === application.stage ? " (current)" : ""}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Recruiter note" hint="Kept with the decision in the audit log (500 characters max).">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          rows={3}
          placeholder="Why this decision? e.g. strong Spark experience, check English level in interview."
          className={inputClass}
        />
      </Field>
      <Button type="submit" className="w-full" loading={pending} disabled={stage === application.stage} icon={<Gavel className="size-4" />}>
        Record decision
      </Button>
    </form>
  );
}
