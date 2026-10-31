"use client";

import Link from "next/link";
import { useActionState, useState } from "react";
import { Building2, UserRound } from "lucide-react";

import { Button, Field, Notice, cx, inputClass } from "@/components/ui";

import { signUp } from "../actions";
import { PasswordInput } from "../login/login-form";

type AccountType = "candidate" | "company";

const TYPES: { value: AccountType; label: string; detail: string; icon: typeof UserRound }[] = [
  { value: "candidate", label: "I'm looking for a job", detail: "Apply and follow your applications", icon: UserRound },
  { value: "company", label: "I'm hiring", detail: "Post jobs and review candidates", icon: Building2 },
];

export function SignupForm({ initialType, next }: { initialType: AccountType; next: string | null }) {
  const [type, setType] = useState<AccountType>(initialType);
  const [state, action, pending] = useActionState(signUp, null);

  return (
    <form action={action} className="space-y-4">
      {next && <input type="hidden" name="next" value={next} />}
      <fieldset>
        <legend className="sr-only">Account type</legend>
        <div className="grid grid-cols-2 gap-2">
          {TYPES.map(({ value, label, detail, icon: Icon }) => (
            <label
              key={value}
              className={cx(
                "flex cursor-pointer flex-col gap-1 rounded-xl border p-3 text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-500",
                type === value
                  ? "border-brand-500 bg-brand-50 dark:border-brand-400 dark:bg-brand-500/10"
                  : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700",
              )}
            >
              <input type="radio" name="account_type" value={value} checked={type === value} onChange={() => setType(value)} className="sr-only" />
              <Icon className={cx("size-5", type === value ? "text-brand-600 dark:text-brand-300" : "text-zinc-400")} aria-hidden />
              <span className="font-medium">{label}</span>
              <span className="text-xs text-zinc-500">{detail}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {state?.error && <Notice tone="red">{state.error}</Notice>}

      {type === "company" && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Company name">
            <input name="company_name" required autoComplete="organization" className={inputClass} />
          </Field>
          <Field label="Your job title" hint="Optional">
            <input name="job_title" autoComplete="organization-title" className={inputClass} placeholder="Talent acquisition" />
          </Field>
        </div>
      )}
      <Field label="Full name">
        <input name="full_name" required autoComplete="name" className={inputClass} />
      </Field>
      <Field label={type === "company" ? "Work email" : "Email"}>
        <input name="email" type="email" required autoComplete="email" defaultValue={state?.email} className={inputClass} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Password" hint="At least 10 characters">
          <PasswordInput name="password" autoComplete="new-password" minLength={10} />
        </Field>
        <Field label="Confirm password">
          <PasswordInput name="confirm" autoComplete="new-password" minLength={10} />
        </Field>
      </div>
      <label className="flex items-start gap-2 text-sm text-zinc-600 dark:text-zinc-300">
        <input type="checkbox" name="terms" required className="mt-0.5 size-4 rounded border-zinc-300 accent-brand-600" />
        <span>
          I have read the{" "}
          <Link href="/privacy" target="_blank" className="font-medium text-brand-700 hover:underline dark:text-brand-300">
            privacy notice
          </Link>
          .
        </span>
      </label>
      {type === "company" && (
        <Notice tone="blue">A platform administrator reviews new companies. You can prepare jobs right away; they appear on the job board once your company is approved.</Notice>
      )}
      <Button type="submit" loading={pending} className="w-full justify-center">
        {type === "company" ? "Create company account" : "Create account"}
      </Button>
    </form>
  );
}
