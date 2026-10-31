"use client";

import { useActionState, useState, useTransition } from "react";
import { KeyRound, MoreHorizontal, Power, UserPlus } from "lucide-react";

import type { FormState } from "@/app/account-actions";
import { FormResult } from "@/components/account-forms";
import { Dialog, Menu } from "@/components/interactive";
import { useActionToast } from "@/components/toaster";
import { Button, Field, Notice, inputClass, selectClass } from "@/components/ui";
import type { Organization, User } from "@/lib/api";

import { createStaffUser, resetUserPassword, setUserActive } from "../actions";

function Secret({ state, onDone }: { state: FormState; onDone: () => void }) {
  return (
    <div className="space-y-3">
      <Notice tone="green">{state?.ok}</Notice>
      <p className="text-sm">Give this temporary password to the person. It is shown only once; they change it from their profile.</p>
      <code className="block select-all rounded-lg bg-zinc-100 px-3 py-2 font-mono text-sm dark:bg-zinc-800">{state?.secret}</code>
      <div className="flex justify-end">
        <Button onClick={onDone}>Done</Button>
      </div>
    </div>
  );
}

export function CreateUserButton({ companies }: { companies: Pick<Organization, "id" | "name">[] }) {
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<"recruiter" | "admin">("recruiter");
  const [state, action, pending] = useActionState(createStaffUser, null);
  const [shown, setShown] = useState<number | undefined>();
  const close = () => {
    setOpen(false);
    setShown(state?.at);
  };
  const created = state?.secret && state.at !== shown;

  return (
    <>
      <Button icon={<UserPlus className="size-4" />} onClick={() => setOpen(true)}>
        Add staff account
      </Button>
      <Dialog open={open} onClose={close} title="Add a staff account" description="A recruiter in a company, or another platform administrator.">
        {created ? (
          <Secret state={state} onDone={close} />
        ) : (
          <form action={action} className="space-y-4">
            <FormResult state={state} />
            <Field label="Role">
              <select name="role" value={role} onChange={(e) => setRole(e.target.value as "recruiter" | "admin")} className={selectClass}>
                <option value="recruiter">Recruiter</option>
                <option value="admin">Platform administrator</option>
              </select>
            </Field>
            {role === "recruiter" && (
              <Field label="Company">
                <select name="organization_id" required className={selectClass} defaultValue="">
                  <option value="" disabled>
                    Choose a company
                  </option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label="Full name">
              <input name="full_name" required className={inputClass} />
            </Field>
            <Field label="Email">
              <input name="email" type="email" required className={inputClass} />
            </Field>
            <Field label="Job title" hint="Optional">
              <input name="job_title" className={inputClass} />
            </Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" loading={pending}>
                Create account
              </Button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  );
}

export function UserActions({ user }: { user: User }) {
  const [, startTransition] = useTransition();
  const toast = useActionToast();
  const [secret, setSecret] = useState<FormState>(null);

  return (
    <>
      <Menu
        label={`Actions for ${user.full_name}`}
        trigger={
          <span className="flex size-8 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100">
            <MoreHorizontal className="size-4" />
          </span>
        }
        items={[
          {
            label: "Reset password",
            icon: <KeyRound />,
            onSelect: () =>
              startTransition(async () => {
                const result = await resetUserPassword(user.id);
                if (result?.secret) setSecret(result);
                else toast(result);
              }),
          },
          {
            label: user.is_active ? "Deactivate" : "Reactivate",
            icon: <Power />,
            danger: user.is_active,
            onSelect: () => startTransition(async () => toast(await setUserActive(user.id, !user.is_active))),
          },
        ]}
      />
      <Dialog open={!!secret} onClose={() => setSecret(null)} title="Temporary password" description={`${user.full_name} was signed out everywhere.`}>
        <Secret state={secret} onDone={() => setSecret(null)} />
      </Dialog>
    </>
  );
}
