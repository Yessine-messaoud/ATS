"use client";

import { useActionState, useState } from "react";
import { Info, Sparkles } from "lucide-react";

import { createJob } from "@/app/actions";
import { JobSteps } from "@/components/job-steps";
import { LongTask } from "@/components/long-task";
import { Button, Notice, Tooltip, cx, inputClass } from "@/components/ui";

const MIN_LENGTH = 50;
const GOOD_LENGTH = 400;

/** Step 1: paste the description; the AI extracts the requirements, then the review page opens (step 2). */
export function NewJobForm() {
  const [state, action, pending] = useActionState(createJob, null);
  const [length, setLength] = useState(0);
  const quality = length < MIN_LENGTH ? "short" : length < GOOD_LENGTH ? "ok" : "good";

  return (
    <form action={action} className="space-y-4">
      <JobSteps current={1} />
      <div>
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <label htmlFor="job-text" className="flex items-center gap-1 font-medium text-zinc-600 dark:text-zinc-300">
            Job description
            <Tooltip content="Paste the full posting: title, location, contract, required and nice-to-have skills, experience, languages.">
              <Info className="size-3.5 text-zinc-400" aria-label="Help" tabIndex={0} />
            </Tooltip>
          </label>
          <span
            className={cx(
              "tabular-nums",
              quality === "short" ? "text-zinc-500" : quality === "ok" ? "text-amber-600" : "text-emerald-600",
            )}
            aria-live="polite"
          >
            {length} characters
            {quality === "short" && ` · ${MIN_LENGTH - length} more needed`}
            {quality === "ok" && " · more detail gives a better extraction"}
          </span>
        </div>
        <textarea
          id="job-text"
          name="text"
          required
          minLength={MIN_LENGTH}
          rows={12}
          disabled={pending}
          onChange={(e) => setLength(e.target.value.trim().length)}
          placeholder={"Data Engineer (CDI) — Tunis, hybrid\n\nRequired: Python, SQL, Spark, 3+ years of experience, English B2.\nNice to have: Kafka, Airflow.\nEducation: Master's or engineering degree."}
          className={cx(inputClass, "min-h-56 font-[450] leading-relaxed")}
          aria-describedby="job-text-hint"
        />
        <p id="job-text-hint" className="mt-1.5 text-xs text-zinc-500">
          The AI only proposes requirements. You review and edit them (skills, minimum experience, education, location,
          contract) before they are used for any ranking.
        </p>
      </div>
      {pending && <LongTask label="Extracting the requirements from the description…" />}
      {state?.error && <Notice tone="red">{state.error}</Notice>}
      <div className="flex justify-end">
        <Button type="submit" loading={pending} disabled={length < MIN_LENGTH} icon={<Sparkles className="size-4" />}>
          {pending ? "Extracting…" : "Extract requirements with AI"}
        </Button>
      </div>
    </form>
  );
}
