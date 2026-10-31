"use client";

import { useActionState, useState } from "react";
import { Sparkles } from "lucide-react";

import { createJob } from "@/app/actions";
import { LongTask } from "@/components/long-task";
import { Button, Notice, inputClass } from "@/components/ui";

const MIN_LENGTH = 50;

export function NewJobForm() {
  const [state, action, pending] = useActionState(createJob, null);
  const [length, setLength] = useState(0);

  return (
    <form action={action} className="space-y-3">
      <textarea
        name="text"
        required
        minLength={MIN_LENGTH}
        rows={10}
        disabled={pending}
        onChange={(e) => setLength(e.target.value.trim().length)}
        placeholder={"Data Engineer (CDI) — Tunis, hybrid\nRequired: Python, SQL, Spark, 3+ years…\nNice to have: Kafka, Airflow"}
        className={inputClass}
        aria-label="Job description"
      />
      {pending && <LongTask label="Extracting the requirements from the description…" />}
      {state?.error && <Notice tone="red">{state.error}</Notice>}
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-zinc-500">
          {length < MIN_LENGTH ? `${MIN_LENGTH - length} more characters needed` : `${length} characters`}
        </span>
        <Button type="submit" loading={pending} disabled={length < MIN_LENGTH} icon={<Sparkles className="size-4" />}>
          {pending ? "Extracting…" : "Create job"}
        </Button>
      </div>
    </form>
  );
}
