"use client";

import { useTransition } from "react";
import { Check, FileSearch, Plus } from "lucide-react";

import { addToPipeline, scoreMatch } from "@/app/actions";
import { useActionToast } from "@/components/toaster";
import { Badge, Button } from "@/components/ui";

export function RankingRowActions({ jobId, candidateId, inPipeline }: { jobId: string; candidateId: string; inPipeline: boolean }) {
  const [scoring, startScoring] = useTransition();
  const [adding, startAdding] = useTransition();
  const toast = useActionToast();

  return (
    <div className="flex items-center justify-start gap-1.5 lg:justify-end">
      <Button
        variant="ghost"
        size="sm"
        loading={scoring}
        icon={<FileSearch className="size-3.5" />}
        title="Score breakdown and an AI-written explanation (takes a few seconds)"
        onClick={() => startScoring(() => scoreMatch(candidateId, jobId))}
      >
        {scoring ? "Explaining…" : "Details"}
      </Button>
      {inPipeline ? (
        <Badge tone="indigo">
          <Check className="size-3" aria-hidden /> In pipeline
        </Badge>
      ) : (
        <Button
          variant="secondary"
          size="sm"
          loading={adding}
          icon={<Plus className="size-3.5" />}
          onClick={() => startAdding(async () => toast(await addToPipeline(jobId, candidateId)))}
        >
          Pipeline
        </Button>
      )}
    </div>
  );
}
