"use client";

import { useTransition } from "react";

import { setJobStatus } from "@/app/actions";
import { Button } from "@/components/ui";

export function JobStatusToggle({ jobId, status }: { jobId: string; status: "open" | "closed" }) {
  const [pending, startTransition] = useTransition();
  const next = status === "open" ? "closed" : "open";
  return (
    <Button variant="secondary" disabled={pending} onClick={() => startTransition(() => setJobStatus(jobId, next))}>
      {status === "open" ? "Close job" : "Reopen job"}
    </Button>
  );
}
