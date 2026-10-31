"use client";

import { useTransition } from "react";
import { Archive, RotateCcw } from "lucide-react";

import { setJobStatus } from "@/app/actions";
import { useToast } from "@/components/toaster";
import { Button } from "@/components/ui";

export function JobStatusToggle({ jobId, status }: { jobId: string; status: "open" | "closed" }) {
  const [pending, startTransition] = useTransition();
  const notify = useToast();
  const next = status === "open" ? "closed" : "open";
  return (
    <Button
      variant="secondary"
      loading={pending}
      icon={status === "open" ? <Archive className="size-4" /> : <RotateCcw className="size-4" />}
      onClick={() =>
        startTransition(async () => {
          await setJobStatus(jobId, next);
          notify(next === "closed" ? "Job closed: it no longer appears in recommendations." : "Job reopened.");
        })
      }
    >
      {status === "open" ? "Close job" : "Reopen job"}
    </Button>
  );
}
