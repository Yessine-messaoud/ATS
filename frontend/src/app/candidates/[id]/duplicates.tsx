"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { mergeCandidates, type ActionState } from "@/app/actions";
import { Button, Notice } from "@/components/ui";
import type { components } from "@/lib/api-types";

type Duplicate = components["schemas"]["DuplicateOut"];

/** Possible duplicates, with a recruiter-confirmed merge into the current record. */
export function Duplicates({ candidateId, duplicates }: { candidateId: string; duplicates: Duplicate[] }) {
  const [confirming, setConfirming] = useState<string>();
  const [state, setState] = useState<ActionState>(null);
  const [pending, startTransition] = useTransition();
  if (duplicates.length === 0 && !state?.ok) return null;

  return (
    <Notice tone="blue">
      <strong>Possible duplicate{duplicates.length > 1 ? "s" : ""}.</strong> The same person may have applied more than once.
      <ul className="mt-2 space-y-2">
        {duplicates.map((d) => (
          <li key={d.candidate_id} className="flex flex-wrap items-center gap-2">
            <Link href={`/candidates/${d.candidate_id}`} className="font-medium underline">
              {d.display_name}
            </Link>
            <span className="text-xs">
              {d.professional_title ?? ""} · {d.reasons.join(", ")} · added {new Date(d.created_at).toLocaleDateString("en-GB")}
            </span>
            {confirming === d.candidate_id ? (
              <>
                <span className="text-xs">Keep this profile and delete the other record (its applications and scores move here)?</span>
                <Button
                  variant="danger"
                  className="px-2 py-0.5 text-xs"
                  disabled={pending}
                  onClick={() => startTransition(async () => setState(await mergeCandidates(candidateId, d.candidate_id)))}
                >
                  Confirm merge
                </Button>
                <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={() => setConfirming(undefined)}>
                  Cancel
                </Button>
              </>
            ) : (
              <Button variant="secondary" className="px-2 py-0.5 text-xs" onClick={() => setConfirming(d.candidate_id)}>
                Merge into this profile
              </Button>
            )}
          </li>
        ))}
      </ul>
      {state?.error && <p className="mt-2 text-xs text-red-700">{state.error}</p>}
      {state?.ok && <p className="mt-2 text-xs">{state.ok}</p>}
    </Notice>
  );
}
