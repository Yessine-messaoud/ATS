"use client";

import { useMemo, useState, useTransition } from "react";
import { ArrowDown, ArrowUp, CheckCircle2, Info, Plus, Save, TriangleAlert, X } from "lucide-react";

import { saveRequirements } from "@/app/actions";
import { EvidenceBadge, Quote } from "@/components/evidence";
import { Slider } from "@/components/interactive";
import { JobSteps } from "@/components/job-steps";
import { useActionToast } from "@/components/toaster";
import { Button, Card, Field, Notice, Tooltip, cx, inputClass, selectClass } from "@/components/ui";
import type { components } from "@/lib/api-types";
import { CONTRACT_TYPES, LANGUAGE_LEVELS, REQUIREMENT_KINDS, SENIORITY, WORK_MODES } from "@/lib/enums";

type JobProfile = components["schemas"]["JobProfile-Output"];
type SkillRequirement = components["schemas"]["SkillRequirement"];
type LanguageRequirement = components["schemas"]["JobLanguageRequirement"];
type EducationRequirement = NonNullable<JobProfile["education_requirements"]>[number];

// Stored as the education requirement's free-text `degree`; the list only makes the common levels one click away.
const EDUCATION_LEVELS = ["High school diploma", "Bachelor's degree", "Master's degree", "Engineering degree", "PhD"];
const pretty = (value: string) => value.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

function EnumSelect<T extends string>({
  value,
  options,
  onChange,
  empty = "Not specified",
  label,
}: {
  value: T | null | undefined;
  options: readonly T[];
  onChange: (value: T | null) => void;
  empty?: string;
  label: string;
}) {
  return (
    <select aria-label={label} value={value ?? ""} onChange={(e) => onChange((e.target.value || null) as T | null)} className={selectClass}>
      <option value="">{empty}</option>
      {options.map((option) => (
        <option key={option} value={option}>
          {pretty(option)}
        </option>
      ))}
    </select>
  );
}

function SkillColumn({
  kind,
  skills,
  onChange,
  onMove,
  onRemove,
  duplicates,
}: {
  kind: SkillRequirement["requirement"];
  skills: { skill: SkillRequirement; index: number }[];
  onChange: (index: number, patch: Partial<SkillRequirement>) => void;
  onMove: (index: number) => void;
  onRemove: (index: number) => void;
  duplicates: Set<string>;
}) {
  const required = kind === "required";
  return (
    <div className={cx("rounded-xl border p-3", required ? "border-brand-200 bg-brand-50/40 dark:border-brand-900 dark:bg-brand-950/20" : "border-zinc-200 dark:border-zinc-800")}>
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        {required ? "Required skills" : "Preferred skills"}
        <span className="rounded-full bg-white px-1.5 text-xs font-medium tabular-nums text-zinc-500 dark:bg-zinc-800">{skills.length}</span>
        <Tooltip content={required ? "A missing required skill lowers the score (×0.92 each)." : "Preferred skills add to the score but are never penalised."}>
          <Info className="size-3.5 text-zinc-400" aria-label="Help" tabIndex={0} />
        </Tooltip>
      </h3>
      {skills.length === 0 && <p className="py-3 text-center text-xs text-zinc-500">None.</p>}
      <ul className="space-y-2">
        {skills.map(({ skill, index }) => {
          const empty = !skill.name.trim();
          const duplicate = duplicates.has(skill.name.trim().toLowerCase());
          return (
            <li key={index} className="rounded-lg border border-zinc-200 bg-white p-2 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center gap-2">
                <input
                  value={skill.name}
                  onChange={(e) => onChange(index, { name: e.target.value })}
                  aria-label="Skill name"
                  aria-invalid={empty || duplicate}
                  placeholder="Skill name"
                  className={cx(inputClass, "h-8 py-1", (empty || duplicate) && "border-red-400 focus:border-red-500 focus:ring-red-500/30")}
                />
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  value={skill.minimum_years ?? ""}
                  onChange={(e) => onChange(index, { minimum_years: e.target.value === "" ? null : Number(e.target.value) })}
                  aria-label={`Minimum years of ${skill.name || "this skill"}`}
                  placeholder="yrs"
                  title="Minimum years with this skill (optional)"
                  className={cx(inputClass, "h-8 w-16 py-1")}
                />
                <Tooltip content={required ? "Move to preferred" : "Move to required"}>
                  <button
                    type="button"
                    onClick={() => onMove(index)}
                    aria-label={required ? `Make ${skill.name} preferred` : `Make ${skill.name} required`}
                    className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800"
                  >
                    {required ? <ArrowDown className="size-4" /> : <ArrowUp className="size-4" />}
                  </button>
                </Tooltip>
                <button
                  type="button"
                  onClick={() => onRemove(index)}
                  aria-label={`Remove ${skill.name || "skill"}`}
                  className="rounded-md p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50"
                >
                  <X className="size-4" />
                </button>
              </div>
              {(empty || duplicate) && <p className="mt-1 text-xs text-red-600">{empty ? "Enter a name or remove the row." : "This skill is listed twice."}</p>}
              {skill.evidence !== undefined && (
                <div className="mt-1.5 flex items-start gap-2">
                  <EvidenceBadge verified={skill.verified} evidence={skill.evidence} />
                  <Quote text={skill.evidence} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function RequirementsEditor({ jobId, initial, validated }: { jobId: string; initial: JobProfile; validated: boolean }) {
  const [profile, setProfile] = useState<JobProfile>(initial);
  const [newSkill, setNewSkill] = useState("");
  const [pending, startTransition] = useTransition();
  const toast = useActionToast();

  const skills = useMemo(() => profile.skill_requirements ?? [], [profile.skill_requirements]);
  const languages = profile.language_requirements ?? [];
  const education = profile.education_requirements ?? [];
  const update = (patch: Partial<JobProfile>) => setProfile((p) => ({ ...p, ...patch }));
  const setSkill = (index: number, patch: Partial<SkillRequirement>) =>
    update({ skill_requirements: skills.map((s, i) => (i === index ? { ...s, ...patch } : s)) });
  const setLanguage = (index: number, patch: Partial<LanguageRequirement>) =>
    update({ language_requirements: languages.map((l, i) => (i === index ? { ...l, ...patch } : l)) });
  const setEducation = (patch: Partial<EducationRequirement> | null) =>
    update({
      education_requirements: patch === null ? education.slice(1) : [{ ...education[0], requirement: education[0]?.requirement ?? "required", ...patch } as EducationRequirement, ...education.slice(1)],
    });

  const dirty = JSON.stringify(profile) !== JSON.stringify(initial);
  const duplicates = useMemo(() => {
    const seen = new Map<string, number>();
    for (const s of skills) {
      const key = s.name.trim().toLowerCase();
      if (key) seen.set(key, (seen.get(key) ?? 0) + 1);
    }
    return new Set([...seen].filter(([, count]) => count > 1).map(([key]) => key));
  }, [skills]);
  const errors = [
    !profile.title.trim() && "The job title is empty.",
    skills.some((s) => !s.name.trim()) && "A skill has no name.",
    duplicates.size > 0 && "Some skills are listed twice.",
    languages.some((l) => !l.language.trim()) && "A language has no name.",
  ].filter(Boolean) as string[];
  const warnings = [
    !skills.some((s) => s.requirement === "required") && "No required skill: every candidate will get full credit on skills.",
  ].filter(Boolean) as string[];

  const addSkill = (kind: SkillRequirement["requirement"]) => {
    const name = newSkill.trim();
    if (!name) return;
    update({ skill_requirements: [...skills, { name, requirement: kind }] });
    setNewSkill("");
  };
  const minYears = profile.experience?.minimum_years ?? 0;
  const degree = education[0]?.degree ?? "";

  const save = () =>
    startTransition(async () => {
      const cleaned = {
        ...profile,
        skill_requirements: skills.filter((s) => s.name.trim()),
        language_requirements: languages.filter((l) => l.language.trim()),
      };
      toast(await saveRequirements(jobId, cleaned));
    });

  return (
    <div className="space-y-5">
      <JobSteps current={validated && !dirty ? 4 : validated ? 3 : 2} />
      {!validated && (
        <Notice tone="blue" icon={<Info />}>
          These requirements were proposed by the AI from the job description. Check them, especially required versus
          preferred, then validate: the validated requirements become the reference for ranking candidates.
        </Notice>
      )}

      <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
        <div className="space-y-5">
          <Card title="Role" description="Title, location and contract as candidates will see them.">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Job title" className="sm:col-span-2 lg:col-span-3">
                <input
                  value={profile.title}
                  onChange={(e) => update({ title: e.target.value })}
                  aria-invalid={!profile.title.trim()}
                  className={cx(inputClass, !profile.title.trim() && "border-red-400")}
                />
              </Field>
              <Field label="City">
                <input value={profile.location?.city ?? ""} onChange={(e) => update({ location: { ...profile.location, city: e.target.value || null } })} className={inputClass} />
              </Field>
              <Field label="Country">
                <input value={profile.location?.country ?? ""} onChange={(e) => update({ location: { ...profile.location, country: e.target.value || null } })} className={inputClass} />
              </Field>
              <Field label="Work mode">
                <EnumSelect label="Work mode" value={profile.work_mode} options={WORK_MODES} onChange={(work_mode) => update({ work_mode })} />
              </Field>
              <Field label="Contract type">
                <EnumSelect label="Contract type" value={profile.contract_type} options={CONTRACT_TYPES} onChange={(contract_type) => update({ contract_type })} />
              </Field>
              <Field label="Seniority">
                <EnumSelect label="Seniority" value={profile.seniority} options={SENIORITY} onChange={(seniority) => update({ seniority })} />
              </Field>
            </div>
          </Card>

          <Card title="Skills" description="Required skills weigh most; a missing one lowers the score. Preferred skills only add.">
            <div className="mb-4 flex flex-wrap gap-2">
              <input
                value={newSkill}
                onChange={(e) => setNewSkill(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addSkill("required");
                  }
                }}
                placeholder="Add a skill, e.g. Kubernetes"
                aria-label="New skill"
                className={cx(inputClass, "min-w-48 flex-1")}
              />
              <Button variant="secondary" disabled={!newSkill.trim()} onClick={() => addSkill("required")} icon={<Plus className="size-4" />}>
                Required
              </Button>
              <Button variant="secondary" disabled={!newSkill.trim()} onClick={() => addSkill("preferred")} icon={<Plus className="size-4" />}>
                Preferred
              </Button>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {REQUIREMENT_KINDS.map((kind) => (
                <SkillColumn
                  key={kind}
                  kind={kind}
                  skills={skills.map((skill, index) => ({ skill, index })).filter(({ skill }) => skill.requirement === kind)}
                  onChange={setSkill}
                  onMove={(index) => setSkill(index, { requirement: skills[index].requirement === "required" ? "preferred" : "required" })}
                  onRemove={(index) => update({ skill_requirements: skills.filter((_, i) => i !== index) })}
                  duplicates={duplicates}
                />
              ))}
            </div>
          </Card>

          <Card
            title="Languages"
            actions={
              <Button size="sm" variant="secondary" icon={<Plus className="size-3.5" />} onClick={() => update({ language_requirements: [...languages, { language: "", requirement: "required" }] })}>
                Add language
              </Button>
            }
          >
            {languages.length === 0 ? (
              <p className="text-sm text-zinc-500">No language requirement.</p>
            ) : (
              <div className="space-y-2">
                {languages.map((language, index) => (
                  <div key={index} className="grid grid-cols-[1fr_8rem_8rem_2.25rem] items-center gap-2">
                    <input
                      value={language.language}
                      aria-label="Language"
                      onChange={(e) => setLanguage(index, { language: e.target.value })}
                      className={cx(inputClass, !language.language.trim() && "border-red-400")}
                    />
                    <EnumSelect
                      label="Requirement"
                      value={language.requirement}
                      options={REQUIREMENT_KINDS}
                      onChange={(requirement) => requirement && setLanguage(index, { requirement })}
                    />
                    <EnumSelect label="Level" value={language.level} options={LANGUAGE_LEVELS} empty="Any level" onChange={(level) => setLanguage(index, { level })} />
                    <button
                      type="button"
                      aria-label={`Remove ${language.language || "language"}`}
                      onClick={() => update({ language_requirements: languages.filter((_, i) => i !== index) })}
                      className="rounded-md p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/50"
                    >
                      <X className="size-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Experience & education">
            <div className="space-y-5">
              <Slider
                label="Minimum experience"
                value={minYears}
                min={0}
                max={15}
                step={0.5}
                format={(v) => (v === 0 ? "None" : `${v} year${v === 1 ? "" : "s"}`)}
                onChange={(v) => update({ experience: { ...profile.experience, minimum_years: v === 0 ? null : v } })}
                hint="Below this, the experience criterion scores lower; it never excludes a candidate on its own."
              />
              <Field label="Education level" hint="Required degree; leave empty if not needed.">
                <select
                  value={degree}
                  onChange={(e) => (e.target.value ? setEducation({ degree: e.target.value }) : setEducation(null))}
                  className={selectClass}
                >
                  <option value="">Not required</option>
                  {EDUCATION_LEVELS.map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                  {degree && !EDUCATION_LEVELS.includes(degree) && <option value={degree}>{degree} (extracted)</option>}
                </select>
              </Field>
              {education[0] && (
                <>
                  <Field label="Field of study">
                    <input
                      value={education[0].field_of_study ?? ""}
                      onChange={(e) => setEducation({ field_of_study: e.target.value || null })}
                      placeholder="e.g. Computer science"
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Degree requirement">
                    <EnumSelect
                      label="Degree requirement"
                      value={education[0].requirement}
                      options={REQUIREMENT_KINDS}
                      onChange={(requirement) => requirement && setEducation({ requirement })}
                    />
                  </Field>
                </>
              )}
            </div>
          </Card>

          <Card title="Check before validating">
            {errors.length === 0 && warnings.length === 0 ? (
              <p className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="size-4" /> Everything looks complete.
              </p>
            ) : (
              <ul className="space-y-2 text-sm">
                {errors.map((error) => (
                  <li key={error} className="flex items-start gap-2 text-red-600">
                    <X className="mt-0.5 size-4 shrink-0" /> {error}
                  </li>
                ))}
                {warnings.map((warning) => (
                  <li key={warning} className="flex items-start gap-2 text-amber-700 dark:text-amber-400">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" /> {warning}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {(dirty || !validated) && (
        <div className="sticky bottom-4 z-20 flex flex-wrap items-center gap-3 rounded-xl border border-brand-200 bg-white px-4 py-3 shadow-lg dark:border-brand-900 dark:bg-zinc-900">
          <span className="text-sm">
            {validated ? "You have unsaved changes." : "Validating publishes these requirements as the reference for ranking."}
          </span>
          <div className="ml-auto flex gap-2">
            {dirty && (
              <Button variant="ghost" disabled={pending} onClick={() => setProfile(initial)}>
                Discard
              </Button>
            )}
            <Button loading={pending} disabled={errors.length > 0} onClick={save} icon={validated ? <Save className="size-4" /> : <CheckCircle2 className="size-4" />}>
              {validated ? "Save changes" : "Validate & publish"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
