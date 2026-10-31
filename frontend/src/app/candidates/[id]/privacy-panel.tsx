"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { Download, ShieldCheck, Trash2 } from "lucide-react";

import { eraseCandidate, setConsent } from "@/app/actions";
import { useActionToast } from "@/components/toaster";
import { Button, Card, Notice, inputClass } from "@/components/ui";

const CONFIRM_WORD = "ERASE";

/** Talent-pool consent, data export and erasure (GDPR rights), with the audit trail one click away. */
export function PrivacyPanel({
  candidateId,
  consent,
  consentUpdatedAt,
  purgeAfter,
}: {
  candidateId: string;
  consent: boolean | null;
  consentUpdatedAt: string | null;
  purgeAfter: string | null;
}) {
  const toast = useActionToast();
  const [erasing, setErasing] = useState(false);
  const [typed, setTyped] = useState("");
  const [reason, setReason] = useState("candidate request");
  const [pending, startTransition] = useTransition();

  const recordConsent = (value: boolean) => startTransition(async () => toast(await setConsent(candidateId, value)));

  return (
    <Card
      title="Privacy"
      actions={
        <Link href={`/audit?entity_id=${candidateId}`} className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline dark:text-brand-400">
          <ShieldCheck className="size-3.5" aria-hidden /> Audit trail
        </Link>
      }
    >
      <div className="space-y-3 text-sm">
        <div>
          <p className="text-xs text-zinc-500">Talent-pool consent (to be matched to jobs the candidate did not apply to)</p>
          <div className="mt-1 flex items-center gap-2">
            <Button
              variant={consent === true ? "primary" : "secondary"}
              className="px-2 py-0.5 text-xs"
              disabled={pending || consent === true}
              onClick={() => recordConsent(true)}
            >
              Given
            </Button>
            <Button
              variant={consent === false ? "danger" : "secondary"}
              className="px-2 py-0.5 text-xs"
              disabled={pending || consent === false}
              onClick={() => recordConsent(false)}
            >
              Refused / withdrawn
            </Button>
            <span className="text-xs text-zinc-500">
              {consent === null
                ? "not asked yet"
                : `recorded ${consentUpdatedAt ? new Date(consentUpdatedAt).toLocaleDateString("en-GB") : ""}`}
            </span>
          </div>
        </div>
        {purgeAfter && (
          <p className="text-xs text-zinc-500">
            The source document is deleted on {new Date(purgeAfter).toLocaleDateString("en-GB")} (retention policy).
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <a
            href={`/candidates/${candidateId}/export`}
            className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline dark:text-brand-400"
          >
            <Download className="size-3.5" aria-hidden /> Export all data (JSON)
          </a>
          {!erasing && (
            <button
              type="button"
              className="flex items-center gap-1 text-xs font-medium text-red-700 hover:underline dark:text-red-400"
              onClick={() => setErasing(true)}
            >
              <Trash2 className="size-3.5" aria-hidden /> Erase candidate…
            </button>
          )}
        </div>
        {erasing && (
          <Notice tone="red">
            <p>
              <strong>Erase everything about this candidate?</strong> Profile, documents, applications, scores and the
              assistant conversations that mention them are deleted. This cannot be undone. The audit log keeps a
              record of the erasure without personal data.
            </p>
            <label className="mt-2 block text-xs">
              Reason (kept in the audit log)
              <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} className={inputClass} />
            </label>
            <label className="mt-2 block text-xs">
              Type {CONFIRM_WORD} to confirm
              <input value={typed} onChange={(e) => setTyped(e.target.value)} className={inputClass} />
            </label>
            <div className="mt-2 flex gap-2">
              <Button
                variant="danger"
                className="px-2 py-0.5 text-xs"
                disabled={pending || typed !== CONFIRM_WORD}
                onClick={() => startTransition(async () => toast(await eraseCandidate(candidateId, reason)))}
              >
                Erase permanently
              </Button>
              <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={() => setErasing(false)}>
                Cancel
              </Button>
            </div>
          </Notice>
        )}
      </div>
    </Card>
  );
}
