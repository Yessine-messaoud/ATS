"use client";

import { useState, useTransition } from "react";

import { saveRequirements, type ActionState } from "@/app/actions";
import { EvidenceBadge, Quote } from "@/components/evidence";
import { Button, Card, Notice, inputClass } from "@/components/ui";
import type { components } from "@/lib/api-types";
import { CONTRACT_TYPES, LANGUAGE_LEVELS, REQUIREMENT_KINDS, SENIORITY, WORK_MODES } from "@/lib/enums";

type JobProfile = components["schemas"]["JobProfile-Output"];
type SkillRequirement = components["schemas"]["SkillRequirement"];
type LanguageRequirement = components["schemas"]["JobLanguageRequirement"];

function Select<T extends string>({
  value,
  options,
  onChange,
  empty = "—",
}: {
  value: T | null | undefined;
  options: readonly T[];
  onChange: (value: T | null) => void;
  empty?: string;
}) {
  return (
    <select value={value ?? ""} onChange={(e) => onChange((e.target.value || null) as T | null)} className={inputClass}>
      <option value="">{empty}</option>
      {options.map((option) => (
        <option key={option} value={option}>
          {option.replace("_", " ")}
        </option>
      ))}
    </select>
  );
}

export function RequirementsEditor({ jobId, initial, validated }: { jobId: string; initial: JobProfile; validated: boolean }) {
  const [profile, setProfile] = useState<JobProfile>(initial);
  const [state, setState] = useState<ActionState>(null);
  const [pending, startTransition] = useTransition();

  const skills = profile.skill_requirements ?? [];
  const languages = profile.language_requirements ?? [];
  const update = (patch: Partial<JobProfile>) => setProfile((p) => ({ ...p, ...patch }));
  const setSkill = (index: number, patch: Partial<SkillRequirement>) =>
    update({ skill_requirements: skills.map((s, i) => (i === index ? { ...s, ...patch } : s)) });
  const setLanguage = (index: number, patch: Partial<LanguageRequirement>) =>
    update({ language_requirements: languages.map((l, i) => (i === index ? { ...l, ...patch } : l)) });

  return (
    <div className="space-y-4">
      {!validated && (
        <Notice>
          These requirements were extracted automatically. Check each one (especially required vs preferred), then
          validate: the validated grid becomes the reference for scoring.
        </Notice>
      )}
      <Card title="Role">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <label className="text-xs text-zinc-500 lg:col-span-2">
            Title
            <input value={profile.title} onChange={(e) => update({ title: e.target.value })} className={inputClass} />
          </label>
          <label className="text-xs text-zinc-500">
            Seniority
            <Select value={profile.seniority} options={SENIORITY} onChange={(seniority) => update({ seniority })} />
          </label>
          <label className="text-xs text-zinc-500">
            Work mode
            <Select value={profile.work_mode} options={WORK_MODES} onChange={(work_mode) => update({ work_mode })} />
          </label>
          <label className="text-xs text-zinc-500">
            Contract
            <Select value={profile.contract_type} options={CONTRACT_TYPES} onChange={(contract_type) => update({ contract_type })} />
          </label>
          <label className="text-xs text-zinc-500">
            Minimum years of experience
            <input
              type="number"
              min={0}
              step={0.5}
              value={profile.experience?.minimum_years ?? ""}
              onChange={(e) =>
                update({
                  experience: { ...profile.experience, minimum_years: e.target.value === "" ? null : Number(e.target.value) },
                })
              }
              className={inputClass}
            />
          </label>
          <label className="text-xs text-zinc-500">
            City
            <input
              value={profile.location?.city ?? ""}
              onChange={(e) => update({ location: { ...profile.location, city: e.target.value || null } })}
              className={inputClass}
            />
          </label>
          <label className="text-xs text-zinc-500">
            Country
            <input
              value={profile.location?.country ?? ""}
              onChange={(e) => update({ location: { ...profile.location, country: e.target.value || null } })}
              className={inputClass}
            />
          </label>
        </div>
      </Card>

      <Card
        title={`Skills (${skills.length})`}
        actions={
          <Button variant="secondary" onClick={() => update({ skill_requirements: [...skills, { name: "", requirement: "required" }] })}>
            Add skill
          </Button>
        }
      >
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-zinc-500">
            <tr>
              <th className="pb-2 font-medium">Skill</th>
              <th className="w-36 pb-2 font-medium">Requirement</th>
              <th className="w-28 pb-2 font-medium">Min. years</th>
              <th className="pb-2 font-medium">Source</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 align-top dark:divide-zinc-800">
            {skills.map((skill, index) => (
              <tr key={index}>
                <td className="py-1.5 pr-2">
                  <input value={skill.name} onChange={(e) => setSkill(index, { name: e.target.value })} className={inputClass} />
                </td>
                <td className="py-1.5 pr-2">
                  <select
                    value={skill.requirement}
                    onChange={(e) => setSkill(index, { requirement: e.target.value as SkillRequirement["requirement"] })}
                    className={inputClass}
                  >
                    {REQUIREMENT_KINDS.map((kind) => (
                      <option key={kind} value={kind}>
                        {kind}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-1.5 pr-2">
                  <input
                    type="number"
                    min={0}
                    step={0.5}
                    value={skill.minimum_years ?? ""}
                    onChange={(e) => setSkill(index, { minimum_years: e.target.value === "" ? null : Number(e.target.value) })}
                    className={inputClass}
                  />
                </td>
                <td className="py-1.5 pr-2">
                  <EvidenceBadge verified={skill.verified} evidence={skill.evidence} />
                  <Quote text={skill.evidence} />
                </td>
                <td className="py-1.5 text-right">
                  <Button
                    variant="ghost"
                    aria-label={`Remove ${skill.name}`}
                    onClick={() => update({ skill_requirements: skills.filter((_, i) => i !== index) })}
                  >
                    ✕
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card
        title={`Languages (${languages.length})`}
        actions={
          <Button
            variant="secondary"
            onClick={() => update({ language_requirements: [...languages, { language: "", requirement: "required" }] })}
          >
            Add language
          </Button>
        }
      >
        <div className="space-y-2">
          {languages.map((language, index) => (
            <div key={index} className="grid grid-cols-[1fr_9rem_9rem_2.5rem] items-center gap-2">
              <input value={language.language} onChange={(e) => setLanguage(index, { language: e.target.value })} className={inputClass} />
              <select
                value={language.requirement}
                onChange={(e) => setLanguage(index, { requirement: e.target.value as LanguageRequirement["requirement"] })}
                className={inputClass}
              >
                {REQUIREMENT_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </select>
              <Select value={language.level} options={LANGUAGE_LEVELS} empty="any level" onChange={(level) => setLanguage(index, { level })} />
              <Button variant="ghost" onClick={() => update({ language_requirements: languages.filter((_, i) => i !== index) })}>
                ✕
              </Button>
            </div>
          ))}
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button
          disabled={pending}
          onClick={() =>
            startTransition(async () => {
              const cleaned = {
                ...profile,
                skill_requirements: skills.filter((s) => s.name.trim()),
                language_requirements: languages.filter((l) => l.language.trim()),
              };
              setState(await saveRequirements(jobId, cleaned));
            })
          }
        >
          {pending ? "Saving…" : validated ? "Save requirements" : "Validate requirements"}
        </Button>
        {state?.error && <Notice tone="red">{state.error}</Notice>}
        {state?.ok && <Notice tone="green">{state.ok}</Notice>}
      </div>
    </div>
  );
}
