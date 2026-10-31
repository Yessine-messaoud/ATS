"use client";

import { useState } from "react";
import { Plus } from "lucide-react";

import { Dialog } from "@/components/interactive";
import { Button } from "@/components/ui";

import { NewJobForm } from "./new-job-form";

export function CreateJobButton({ startOpen = false }: { startOpen?: boolean }) {
  const [open, setOpen] = useState(startOpen);
  return (
    <>
      <Button onClick={() => setOpen(true)} icon={<Plus className="size-4" />}>
        Create job
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        size="lg"
        title="Create a new job"
        description="Paste the job description: the AI extracts the requirements, then you review, edit and validate them."
      >
        <NewJobForm />
      </Dialog>
    </>
  );
}
