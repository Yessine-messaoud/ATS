"use client";

import Link from "next/link";
import { useActionState, useState } from "react";
import { FileUp, Send, ShieldCheck } from "lucide-react";

import { FormResult } from "@/components/account-forms";
import { Button, cx } from "@/components/ui";

import { applyToJob } from "../../actions";

const ACCEPT = ".pdf,.docx,.txt,.eml,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** Apply with a new CV, or (when a profile is on file) with the existing one. */
export function ApplyForm({ jobId, profileFile }: { jobId: string; profileFile: string | null }) {
  const [state, action, pending] = useActionState(applyToJob, null);
  const [file, setFile] = useState<string | null>(null);
  const [replace, setReplace] = useState(!profileFile);

  return (
    <form action={action} className="space-y-4">
      <input type="hidden" name="job_id" value={jobId} />
      <FormResult state={state} />
      {profileFile && !replace ? (
        <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
          <p>
            We will send your profile from <span className="font-medium">{profileFile}</span>.
          </p>
          <button type="button" onClick={() => setReplace(true)} className="mt-1 text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
            Send a new CV instead
          </button>
        </div>
      ) : (
        <label
          className={cx(
            "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-500",
            file ? "border-brand-400 bg-brand-50/60 dark:border-brand-600 dark:bg-brand-500/10" : "border-zinc-300 hover:border-brand-300 dark:border-zinc-700",
          )}
        >
          <FileUp className="size-6 text-brand-600 dark:text-brand-300" aria-hidden />
          <span className="font-medium">{file ?? "Choose your CV"}</span>
          <span className="text-xs text-zinc-500">PDF or Word, up to 10 MB</span>
          <input name="file" type="file" accept={ACCEPT} required className="sr-only" onChange={(e) => setFile(e.target.files?.[0]?.name ?? null)} />
        </label>
      )}
      {replace && (
        <label className="flex items-start gap-2 text-sm text-zinc-600 dark:text-zinc-300">
          <input type="checkbox" name="talent_pool_consent" className="mt-0.5 size-4 accent-brand-600" />
          <span>Let other companies on RecruitAI find my profile for their jobs. You can change this at any time.</span>
        </label>
      )}
      <p className="flex gap-2 rounded-lg bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-300">
        <ShieldCheck className="size-4 shrink-0 text-brand-600 dark:text-brand-300" aria-hidden />
        <span>
          Software reads your CV to build a profile you can check and correct. A recruiter, not the software, decides on your application.{" "}
          <Link href="/privacy" target="_blank" className="font-medium underline">
            Privacy notice
          </Link>
        </span>
      </p>
      <Button type="submit" loading={pending} icon={<Send className="size-4" />} className="w-full">
        Send my application
      </Button>
    </form>
  );
}
