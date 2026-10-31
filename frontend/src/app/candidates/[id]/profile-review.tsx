"use client";

import { useState, useTransition, type ReactNode } from "react";

import { Save, Undo2 } from "lucide-react";

import { saveCandidateProfile } from "@/app/actions";
import { useActionToast } from "@/components/toaster";
import { EvidenceBadge, Quote } from "@/components/evidence";
import { Button, Card, Notice, inputClass } from "@/components/ui";
import type { components } from "@/lib/api-types";
import { LANGUAGE_LEVELS, SENIORITY } from "@/lib/enums";

type Profile = components["schemas"]["CandidateProfile"];
type Evidenced = { evidence?: string | null; verified?: boolean | null; confidence?: number | null };
type ListKey = "skills" | "experiences" | "education" | "certifications" | "languages" | "projects";

/** One extracted item with its evidence, and recruiter controls to confirm an unverified claim or remove it. */
function Item({
  item,
  children,
  onConfirm,
  onRemove,
}: {
  item: Evidenced;
  children: ReactNode;
  onConfirm: () => void;
  onRemove: () => void;
}) {
  return (
    <li
      className={
        item.verified === false
          ? "rounded-md border border-red-200 bg-red-50/50 p-2 dark:border-red-900 dark:bg-red-950/30"
          : "rounded-md border border-zinc-200 p-2 dark:border-zinc-800"
      }
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 text-sm">{children}</div>
        <div className="flex shrink-0 items-center gap-1">
          <EvidenceBadge verified={item.verified} evidence={item.evidence} />
          {item.verified === false && (
            <Button variant="secondary" className="px-2 py-0.5 text-xs" onClick={onConfirm} title="I checked the document: this is correct">
              Confirm
            </Button>
          )}
          <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={onRemove} aria-label="Remove">
            ✕
          </Button>
        </div>
      </div>
      <Quote text={item.evidence} />
    </li>
  );
}

export function ProfileReview({ candidateId, initial }: { candidateId: string; initial: Profile }) {
  const [profile, setProfile] = useState<Profile>(initial);
  const [pending, startTransition] = useTransition();
  const toast = useActionToast();
  const dirty = JSON.stringify(profile) !== JSON.stringify(initial);

  const update = (patch: Partial<Profile>) => setProfile((p) => ({ ...p, ...patch }));
  function list<K extends ListKey>(key: K): NonNullable<Profile[K]> {
    return (profile[key] ?? []) as NonNullable<Profile[K]>;
  }
  const setList = <K extends ListKey>(key: K, items: NonNullable<Profile[K]>) => update({ [key]: items } as Partial<Profile>);
  const controls = <K extends ListKey>(key: K, index: number) => ({
    onConfirm: () =>
      setList(key, (list(key) as Evidenced[]).map((x, i) => (i === index ? { ...x, verified: true } : x)) as NonNullable<Profile[K]>),
    onRemove: () => setList(key, (list(key) as Evidenced[]).filter((_, i) => i !== index) as NonNullable<Profile[K]>),
  });
  const unverified = (["skills", "experiences", "education", "certifications", "languages", "projects"] as const).reduce(
    (count, key) => count + (list(key) as Evidenced[]).filter((x) => x.verified === false).length,
    0,
  );

  return (
    <div className="space-y-4">
      {unverified > 0 && (
        <Notice>
          {unverified} item(s) could not be found in the source document. They earn <strong>no credit</strong> in matching
          until you confirm them, or remove them if they are wrong.
        </Notice>
      )}

      <Card title="Summary">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs text-zinc-500 sm:col-span-2">
            Professional title
            <input
              value={profile.professional_title ?? ""}
              onChange={(e) => update({ professional_title: e.target.value || null })}
              className={inputClass}
            />
          </label>
          <label className="text-xs text-zinc-500">
            Seniority
            <select
              value={profile.seniority ?? ""}
              onChange={(e) => update({ seniority: (e.target.value || null) as Profile["seniority"] })}
              className={inputClass}
            >
              <option value="">derived from experience</option>
              {SENIORITY.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-zinc-500 sm:col-span-3">
            Location
            <input
              value={[profile.identity?.location?.city, profile.identity?.location?.country].filter(Boolean).join(", ")}
              readOnly
              className={`${inputClass} bg-zinc-50 dark:bg-zinc-900`}
            />
          </label>
        </div>
      </Card>

      <Card title={`Skills (${list("skills").length})`}>
        <ul className="grid gap-2 sm:grid-cols-2">
          {list("skills").map((skill, index) => (
            <Item key={`${skill.name}-${index}`} item={skill} {...controls("skills", index)}>
              <span className="font-medium">{skill.name}</span>
              {skill.category && <span className="ml-1 text-xs text-zinc-500">{skill.category.replace("_", " ")}</span>}
            </Item>
          ))}
        </ul>
      </Card>

      <Card title={`Experience (${list("experiences").length})`}>
        <ul className="space-y-2">
          {list("experiences").map((experience, index) => (
            <Item key={`${experience.company}-${index}`} item={experience} {...controls("experiences", index)}>
              <div className="font-medium">
                {experience.job_title} · {experience.company}
              </div>
              <div className="text-xs text-zinc-500">
                {experience.dates?.start_date ?? "?"} → {experience.current ? "present" : experience.dates?.end_date ?? "?"}
              </div>
              {!!experience.responsibilities?.length && (
                <ul className="mt-1 list-disc pl-4 text-xs text-zinc-600 dark:text-zinc-400">
                  {experience.responsibilities.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
            </Item>
          ))}
        </ul>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Education">
          <ul className="space-y-2">
            {list("education").map((education, index) => (
              <Item key={`${education.institution}-${index}`} item={education} {...controls("education", index)}>
                <div className="font-medium">{education.degree ?? "Degree"}</div>
                <div className="text-xs text-zinc-500">
                  {education.institution}
                  {education.field_of_study ? ` · ${education.field_of_study}` : ""}
                </div>
              </Item>
            ))}
          </ul>
        </Card>
        <Card title="Languages & certifications">
          <ul className="space-y-2">
            {list("languages").map((language, index) => (
              <Item key={`${language.language}-${index}`} item={language} {...controls("languages", index)}>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{language.language}</span>
                  <select
                    aria-label={`${language.language} level`}
                    value={language.level ?? ""}
                    onChange={(e) =>
                      setList(
                        "languages",
                        list("languages").map((l, i) =>
                          i === index ? { ...l, level: (e.target.value || null) as typeof l.level } : l,
                        ),
                      )
                    }
                    className={`${inputClass} w-28 py-0.5 text-xs`}
                  >
                    <option value="">level unknown</option>
                    {LANGUAGE_LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </div>
              </Item>
            ))}
            {list("certifications").map((certification, index) => (
              <Item key={`${certification.name}-${index}`} item={certification} {...controls("certifications", index)}>
                <span className="font-medium">{certification.name}</span>
              </Item>
            ))}
          </ul>
        </Card>
      </div>

      {dirty && (
        <div className="sticky bottom-4 z-20 flex flex-wrap items-center gap-3 rounded-xl border border-indigo-200 bg-white px-4 py-3 shadow-lg dark:border-indigo-900 dark:bg-zinc-900">
          <span className="text-sm font-medium">You have unsaved changes</span>
          <span className="hidden text-xs text-zinc-500 sm:inline">Corrections are kept as feedback to evaluate the extractor.</span>
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" disabled={pending} onClick={() => setProfile(initial)} icon={<Undo2 className="size-4" />}>
              Discard
            </Button>
            <Button
              loading={pending}
              icon={<Save className="size-4" />}
              onClick={() => startTransition(async () => toast(await saveCandidateProfile(candidateId, profile)))}
            >
              Save review
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
