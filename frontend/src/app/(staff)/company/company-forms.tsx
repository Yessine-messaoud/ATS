"use client";

import { useActionState, useState, useTransition } from "react";
import { Save, UserPlus } from "lucide-react";

import { addMember, setMemberActive, updateOrganization } from "@/app/account-actions";
import { FormResult } from "@/components/account-forms";
import { Avatar } from "@/components/avatar";
import { Dialog } from "@/components/interactive";
import { useActionToast } from "@/components/toaster";
import { Badge, Button, Field, Notice, inputClass, selectClass } from "@/components/ui";
import type { Organization, User } from "@/lib/api";
import { formatDate } from "@/lib/format";

const SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"];

export function CompanyForm({ organization }: { organization: Organization }) {
  const [state, action, pending] = useActionState(updateOrganization, null);
  return (
    <form action={action} className="space-y-4">
      <FormResult state={state} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name" className="sm:col-span-2">
          <input name="name" required defaultValue={organization.name} autoComplete="organization" className={inputClass} />
        </Field>
        <Field label="Industry">
          <input name="industry" defaultValue={organization.industry ?? ""} placeholder="Banking, software, telecom…" className={inputClass} />
        </Field>
        <Field label="Company size">
          <select name="size" defaultValue={organization.size ?? ""} className={selectClass}>
            <option value="">Not specified</option>
            {SIZES.map((size) => (
              <option key={size} value={size}>
                {size} employees
              </option>
            ))}
          </select>
        </Field>
        <Field label="City">
          <input name="city" defaultValue={organization.city ?? ""} className={inputClass} />
        </Field>
        <Field label="Website">
          <input name="website" type="url" defaultValue={organization.website ?? ""} placeholder="https://" className={inputClass} />
        </Field>
        <Field label="About the company" hint="A few sentences for candidates." className="sm:col-span-2">
          <textarea name="description" rows={5} maxLength={4000} defaultValue={organization.description ?? ""} className={inputClass} />
        </Field>
      </div>
      <div className="flex justify-end">
        <Button type="submit" loading={pending} icon={<Save className="size-4" />}>
          Save company profile
        </Button>
      </div>
    </form>
  );
}

function AddMember() {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState(addMember, null);
  return (
    <>
      <Button size="sm" variant="secondary" icon={<UserPlus className="size-4" />} onClick={() => setOpen(true)}>
        Add recruiter
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title="Add a recruiter" description="They join your company and see the same jobs and candidates.">
        {state?.secret ? (
          <div className="space-y-3">
            <Notice tone="green">{state.ok}</Notice>
            <p className="text-sm">Give them this temporary password. It is shown only once; they can change it in their profile.</p>
            <code className="block select-all rounded-lg bg-zinc-100 px-3 py-2 font-mono text-sm dark:bg-zinc-800">{state.secret}</code>
            <div className="flex justify-end">
              <Button onClick={() => setOpen(false)}>Done</Button>
            </div>
          </div>
        ) : (
          <form action={action} className="space-y-4">
            <FormResult state={state} />
            <Field label="Full name">
              <input name="full_name" required className={inputClass} />
            </Field>
            <Field label="Work email">
              <input name="email" type="email" required className={inputClass} />
            </Field>
            <Field label="Job title" hint="Optional">
              <input name="job_title" className={inputClass} />
            </Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
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

export function TeamList({ members, selfId }: { members: User[]; selfId: string }) {
  const [pending, startTransition] = useTransition();
  const toast = useActionToast();
  return (
    <div>
      <div className="flex justify-end border-b border-zinc-100 px-4 py-2 dark:border-zinc-800">
        <AddMember />
      </div>
      <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {members.map((member) => (
          <li key={member.id} className="flex items-center gap-3 px-4 py-3">
            <Avatar id={member.id} name={member.full_name} size="sm" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {member.full_name}
                {member.id === selfId && <span className="ml-1 text-xs font-normal text-zinc-500">(you)</span>}
              </span>
              <span className="block truncate text-xs text-zinc-500">
                {member.job_title ? `${member.job_title} · ` : ""}
                {member.last_login_at ? `last sign-in ${formatDate(member.last_login_at)}` : "never signed in"}
              </span>
            </span>
            {!member.is_active && <Badge tone="red">deactivated</Badge>}
            {member.id !== selfId && (
              <Button
                size="sm"
                variant="ghost"
                disabled={pending}
                onClick={() => startTransition(async () => toast(await setMemberActive(member.id, !member.is_active)))}
              >
                {member.is_active ? "Deactivate" : "Reactivate"}
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
