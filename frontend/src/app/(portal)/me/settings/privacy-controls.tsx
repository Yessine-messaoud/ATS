"use client";

import { useActionState, useState, useTransition } from "react";
import { Trash2 } from "lucide-react";

import { FormResult } from "@/components/account-forms";
import { Dialog } from "@/components/interactive";
import { useActionToast } from "@/components/toaster";
import { Button, Field, cx, inputClass } from "@/components/ui";
import { PasswordInput } from "@/app/(auth)/login/login-form";

import { deleteAccount, setTalentPool } from "../../actions";

const OPTIONS = [
  { value: false, title: "Only companies I apply to", detail: "Your profile is shared with a company when you apply to one of its jobs." },
  { value: true, title: "All companies on RecruitAI", detail: "Companies can also find you for jobs you have not applied to." },
];

export function TalentPoolToggle({ consent, hasProfile }: { consent: boolean | null; hasProfile: boolean }) {
  const [value, setValue] = useState(consent === true);
  const [pending, startTransition] = useTransition();
  const toast = useActionToast();
  if (!hasProfile) return <p className="text-sm text-zinc-500">You can choose this once your CV has been read.</p>;
  return (
    <fieldset disabled={pending} className="grid gap-2 sm:grid-cols-2">
      <legend className="sr-only">Profile visibility</legend>
      {OPTIONS.map((option) => (
        <label
          key={String(option.value)}
          className={cx(
            "cursor-pointer rounded-xl border p-3 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-500",
            value === option.value ? "border-brand-500 bg-brand-50 dark:border-brand-400 dark:bg-brand-500/10" : "border-zinc-200 dark:border-zinc-800",
          )}
        >
          <input
            type="radio"
            name="visibility"
            className="sr-only"
            checked={value === option.value}
            onChange={() => {
              setValue(option.value);
              startTransition(async () => toast(await setTalentPool(option.value)));
            }}
          />
          <span className="block font-medium">{option.title}</span>
          <span className="block text-xs text-zinc-500">{option.detail}</span>
        </label>
      ))}
    </fieldset>
  );
}

export function DeleteAccount() {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState(deleteAccount, null);
  return (
    <>
      <Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setOpen(true)}>
        Delete my account
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title="Delete your account?" description="Your account, profile, CV and every application are erased. Companies can no longer see them.">
        <form action={action} className="space-y-4">
          <FormResult state={state} />
          <Field label="Your password">
            <PasswordInput name="password" autoComplete="current-password" />
          </Field>
          <Field label="Type DELETE to confirm">
            <input name="confirm" required autoComplete="off" className={inputClass} />
          </Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="danger" loading={pending}>
              Delete everything
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
