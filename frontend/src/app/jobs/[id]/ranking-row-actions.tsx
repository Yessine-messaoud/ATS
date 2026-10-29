"use client";

import { useState, useTransition } from "react";

import { addToPipeline, scoreMatch } from "@/app/actions";
import { Button } from "@/components/ui";

export function RankingRowActions({
  jobId,
  candidateId,
  inPipeline,
}: {
  jobId: string;
  candidateId: string;
  inPipeline: boolean;
}) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string>();

  return (
    <div className="flex justify-end gap-1">
      <Button variant="ghost" disabled={pending} onClick={() => startTransition(() => scoreMatch(candidateId, jobId))}>
        Details
      </Button>
      <Button
        variant="secondary"
        disabled={pending || inPipeline}
        title={error}
        onClick={() =>
          startTransition(async () => {
            const result = await addToPipeline(jobId, candidateId);
            setError(result?.error);
          })
        }
      >
        {inPipeline ? "In pipeline" : "Add to pipeline"}
      </Button>
    </div>
  );
}
