"use client";

import { useActionState } from "react";
import { KeyRound, Save } from "lucide-react";

import { changePassword, updateProfile, type FormState } from "@/app/account-actions";
import { PasswordInput } from "@/app/(auth)/login/login-form";
import type { User } from "@/lib/api";

import { Button, Field, Notice, inputClass, selectClass } from "./ui";

export function FormResult({ state }: { state: FormState }) {
  if (state?.error) return <Notice tone="red">{state.error}</Notice>;
  if (state?.ok) return <Notice tone="green">{state.ok}</Notice>;
  return null;
}

function Toggle({ name, label, detail, defaultChecked }: { name: string; label: string; detail: string; defaultChecked: boolean }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-zinc-500">{detail}</span>
      </span>
      <input type="checkbox" name={name} defaultChecked={defaultChecked} className="peer sr-only" />
      <span
        aria-hidden
        className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full bg-zinc-300 transition-colors after:absolute after:left-0.5 after:top-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:bg-brand-600 peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500 dark:bg-zinc-700"
      />
    </label>
  );
}

/** Name, contact, language and (staff) notification preferences. */
export function ProfileForm({ user }: { user: User }) {
  const [state, action, pending] = useActionState(updateProfile, null);
  const staff = user.role !== "candidate";
  const prefs = user.preferences as { email_digest?: boolean; notify_new_applications?: boolean };
  return (
    <form action={action} className="space-y-4">
      <FormResult state={state} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name">
          <input name="full_name" required defaultValue={user.full_name} autoComplete="name" className={inputClass} />
        </Field>
        <Field label="Email" hint="Used to sign in. Ask an administrator to change it.">
          <input value={user.email} readOnly disabled className={inputClass} />
        </Field>
        {staff && (
          <Field label="Job title">
            <input name="job_title" defaultValue={user.job_title ?? ""} placeholder="Talent acquisition lead" className={inputClass} />
          </Field>
        )}
        <Field label="Phone" hint="Optional">
          <input name="phone" type="tel" defaultValue={user.phone ?? ""} autoComplete="tel" className={inputClass} />
        </Field>
        <Field label="Language">
          <select name="locale" defaultValue={user.locale} className={selectClass}>
            <option value="en">English</option>
            <option value="fr">Français (interface in English for now)</option>
          </select>
        </Field>
      </div>
      {staff && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-zinc-600 dark:text-zinc-300">Notifications</p>
          <Toggle
            name="notify_new_applications"
            label="New applications"
            detail="Show applications received through the job board in your notifications."
            defaultChecked={prefs.notify_new_applications ?? true}
          />
          <Toggle name="email_digest" label="Weekly email digest" detail="Saved for when email sending is set up." defaultChecked={prefs.email_digest ?? false} />
        </div>
      )}
      <div className="flex justify-end">
        <Button type="submit" loading={pending} icon={<Save className="size-4" />}>
          Save profile
        </Button>
      </div>
    </form>
  );
}

export function PasswordForm() {
  const [state, action, pending] = useActionState(changePassword, null);
  return (
    <form action={action} className="space-y-4" key={state?.ok ? state.at : "form"}>
      <FormResult state={state} />
      <Field label="Current password">
        <PasswordInput name="current_password" autoComplete="current-password" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="New password" hint="At least 10 characters">
          <PasswordInput name="new_password" autoComplete="new-password" minLength={10} />
        </Field>
        <Field label="Confirm new password">
          <PasswordInput name="confirm" autoComplete="new-password" minLength={10} />
        </Field>
      </div>
      <div className="flex justify-end">
        <Button type="submit" variant="secondary" loading={pending} icon={<KeyRound className="size-4" />}>
          Change password
        </Button>
      </div>
    </form>
  );
}
