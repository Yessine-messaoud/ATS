"use client";

import { useActionState } from "react";

import { createJob } from "@/app/actions";
import { Button, Notice, inputClass } from "@/components/ui";

export function NewJobForm() {
  const [state, action, pending] = useActionState(createJob, null);

  return (
    <form action={action} className="space-y-3">
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Paste the full job description. Requirements are extracted automatically, then you review and validate them.
      </p>
      <textarea
        name="text"
        required
        minLength={50}
        rows={12}
        placeholder="Data Engineer (CDI), Tunis. Required: Python, SQL…"
        className={inputClass}
      />
      {state?.error && <Notice tone="red">{state.error}</Notice>}
      <Button type="submit" disabled={pending}>
        {pending ? "Extracting requirements…" : "Create job"}
      </Button>
    </form>
  );
}
