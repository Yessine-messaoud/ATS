"use client";

import { useActionState, useState } from "react";
import { Eye, EyeOff, LogIn } from "lucide-react";

import { Button, Field, Notice, cx, inputClass } from "@/components/ui";

import { signIn } from "../actions";

export function PasswordInput({ name, autoComplete, minLength }: { name: string; autoComplete: string; minLength?: number }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input name={name} type={visible ? "text" : "password"} required autoComplete={autoComplete} minLength={minLength} className={cx(inputClass, "pr-10")} />
      <button
        type="button"
        onClick={() => setVisible(!visible)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

export function LoginForm({ next }: { next: string | null }) {
  const [state, action, pending] = useActionState(signIn, null);
  return (
    <form action={action} className="space-y-4">
      {next && <input type="hidden" name="next" value={next} />}
      {state?.error && <Notice tone="red">{state.error}</Notice>}
      <Field label="Email">
        <input name="email" type="email" required autoComplete="email" defaultValue={state?.email} className={inputClass} autoFocus />
      </Field>
      <Field label="Password">
        <PasswordInput name="password" autoComplete="current-password" />
      </Field>
      <Button type="submit" loading={pending} icon={<LogIn className="size-4" />} className="w-full justify-center">
        Sign in
      </Button>
    </form>
  );
}
