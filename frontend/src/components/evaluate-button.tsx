"use client";

import { useTransition } from "react";
import { FileSearch } from "lucide-react";

import { scoreMatch } from "@/app/actions";

import { Button } from "./ui";

/** Opens a full evaluation: deterministic score breakdown plus an AI-written summary (takes a few seconds). */
export function EvaluateButton({ candidateId, jobId, label = "Evaluate", variant = "secondary" }: { candidateId: string; jobId: string; label?: string; variant?: "primary" | "secondary" | "ghost" }) {
  const [pending, startTransition] = useTransition();
  return (
    <Button
      size="sm"
      variant={variant}
      loading={pending}
      icon={<FileSearch className="size-3.5" />}
      title="Score breakdown and AI-written summary (takes a few seconds with the local model)"
      onClick={() => startTransition(() => scoreMatch(candidateId, jobId))}
    >
      {pending ? "Evaluating…" : label}
    </Button>
  );
}
