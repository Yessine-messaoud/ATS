"use client";

import { useActionState, useState, useTransition } from "react";
import { FileUp, Plus, Save, Undo2, X } from "lucide-react";

import { FormResult } from "@/components/account-forms";
import { useActionToast } from "@/components/toaster";
import { Badge, Button, Card, Field, cx, inputClass } from "@/components/ui";
import type { CandidateProfile } from "@/lib/api";

import { replaceCv, saveMyProfile } from "../../actions";

type Evidenced = { verified?: boolean | null };

function Declared({ item }: { item: Evidenced }) {
  return item.verified === false ? (
    <Badge tone="amber" title="Not found in your CV: shown to recruiters, not counted in matching">
      declared by you
    </Badge>
  ) : null;
}

function Removable({ children, onRemove, item }: { children: React.ReactNode; onRemove: () => void; item: Evidenced }) {
  return (
    <li className="flex items-start justify-between gap-2 rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <div className="min-w-0 flex-1 text-sm">{children}</div>
      <Declared item={item} />
      <button type="button" onClick={onRemove} aria-label="Remove" className="rounded p-0.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800">
        <X className="size-4" />
      </button>
    </li>
  );
}

export function MyProfileEditor({ initial }: { initial: CandidateProfile }) {
  const [profile, setProfile] = useState(initial);
  const [skill, setSkill] = useState("");
  const [pending, startTransition] = useTransition();
  const toast = useActionToast();
  const dirty = JSON.stringify(profile) !== JSON.stringify(initial);
  const identity = profile.identity ?? {};
  const setIdentity = (patch: Partial<NonNullable<CandidateProfile["identity"]>>) => setProfile((p) => ({ ...p, identity: { ...identity, ...patch } }));
  const remove = <K extends "skills" | "experiences" | "education" | "languages" | "certifications">(key: K, index: number) =>
    setProfile((p) => ({ ...p, [key]: (p[key] ?? []).filter((_, i) => i !== index) }));
  const addSkill = () => {
    const name = skill.trim();
    if (!name || (profile.skills ?? []).some((s) => s.name.toLowerCase() === name.toLowerCase())) return;
    setProfile((p) => ({ ...p, skills: [...(p.skills ?? []), { name, verified: false }] }));
    setSkill("");
  };

  return (
    <div className="space-y-6">
      <Card title="About me">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name">
            <input value={identity.full_name ?? ""} onChange={(e) => setIdentity({ full_name: e.target.value || null })} className={inputClass} />
          </Field>
          <Field label="Headline">
            <input value={profile.professional_title ?? ""} onChange={(e) => setProfile({ ...profile, professional_title: e.target.value || null })} placeholder="Data engineer" className={inputClass} />
          </Field>
          <Field label="Email shown to companies">
            <input type="email" value={identity.email ?? ""} onChange={(e) => setIdentity({ email: e.target.value || null })} className={inputClass} />
          </Field>
          <Field label="Phone">
            <input value={identity.phone ?? ""} onChange={(e) => setIdentity({ phone: e.target.value || null })} className={inputClass} />
          </Field>
          <Field label="Summary" className="sm:col-span-2">
            <textarea rows={4} value={profile.professional_summary ?? ""} onChange={(e) => setProfile({ ...profile, professional_summary: e.target.value || null })} className={inputClass} />
          </Field>
        </div>
      </Card>

      <Card title="Skills" description={`${(profile.skills ?? []).length} skills`}>
        <ul className="flex flex-wrap gap-2">
          {(profile.skills ?? []).map((s, index) => (
            <li
              key={`${s.name}-${index}`}
              className={cx(
                "flex items-center gap-1 rounded-full border py-1 pl-3 pr-1 text-sm",
                s.verified === false ? "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40" : "border-zinc-200 dark:border-zinc-700",
              )}
              title={s.verified === false ? "Declared by you: not counted in matching until it appears in your CV" : undefined}
            >
              {s.name}
              <button type="button" onClick={() => remove("skills", index)} aria-label={`Remove ${s.name}`} className="rounded-full p-0.5 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700 dark:hover:bg-zinc-700">
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex gap-2">
          <input
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addSkill())}
            placeholder="Add a skill"
            aria-label="Add a skill"
            className={cx(inputClass, "max-w-xs")}
          />
          <Button type="button" variant="secondary" icon={<Plus className="size-4" />} onClick={addSkill}>
            Add
          </Button>
        </div>
      </Card>

      <Card title="Experience">
        {(profile.experiences ?? []).length === 0 ? (
          <p className="text-sm text-zinc-500">No experience was read from your CV.</p>
        ) : (
          <ul className="space-y-2">
            {(profile.experiences ?? []).map((e, index) => (
              <Removable key={index} item={e} onRemove={() => remove("experiences", index)}>
                <span className="font-medium">{e.job_title}</span>
                {e.company && <span className="text-zinc-500"> · {e.company}</span>}
                {(e.dates?.start_date || e.dates?.end_date || e.current) && (
                  <span className="block text-xs text-zinc-500">
                    {e.dates?.start_date ?? "?"} – {e.current ? "present" : (e.dates?.end_date ?? "?")}
                  </span>
                )}
              </Removable>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Education">
          {(profile.education ?? []).length === 0 ? (
            <p className="text-sm text-zinc-500">None read from your CV.</p>
          ) : (
            <ul className="space-y-2">
              {(profile.education ?? []).map((e, index) => (
                <Removable key={index} item={e} onRemove={() => remove("education", index)}>
                  <span className="font-medium">{e.degree ?? e.field_of_study ?? "Degree"}</span>
                  {e.institution && <span className="block text-xs text-zinc-500">{e.institution}</span>}
                </Removable>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Languages">
          {(profile.languages ?? []).length === 0 ? (
            <p className="text-sm text-zinc-500">None read from your CV.</p>
          ) : (
            <ul className="space-y-2">
              {(profile.languages ?? []).map((l, index) => (
                <Removable key={index} item={l} onRemove={() => remove("languages", index)}>
                  {l.language}
                  {l.level && <span className="text-zinc-500"> · {l.level}</span>}
                </Removable>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="sticky bottom-4 flex justify-end gap-2">
        {dirty && (
          <Button type="button" variant="secondary" icon={<Undo2 className="size-4" />} onClick={() => setProfile(initial)}>
            Undo changes
          </Button>
        )}
        <Button type="button" disabled={!dirty} loading={pending} icon={<Save className="size-4" />} onClick={() => startTransition(async () => toast(await saveMyProfile(profile)))}>
          Save my profile
        </Button>
      </div>
    </div>
  );
}

export function ReplaceCv() {
  const [state, action, pending] = useActionState(replaceCv, null);
  const [file, setFile] = useState<string | null>(null);
  return (
    <form action={action} className="space-y-3" key={state?.at ?? "cv"}>
      <FormResult state={state} />
      <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-zinc-300 px-3 py-3 text-sm hover:border-brand-300 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-500 dark:border-zinc-700">
        <FileUp className="size-5 text-brand-600 dark:text-brand-300" aria-hidden />
        <span className="min-w-0 flex-1 truncate">{file ?? "Choose a PDF or Word file"}</span>
        <input name="file" type="file" required accept=".pdf,.docx,.txt" className="sr-only" onChange={(e) => setFile(e.target.files?.[0]?.name ?? null)} />
      </label>
      <Button type="submit" variant="secondary" loading={pending} className="w-full">
        Send new CV
      </Button>
    </form>
  );
}
