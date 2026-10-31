"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Briefcase, MapPin, Plus, Search, X } from "lucide-react";

import { Badge, Button, Card, Empty, cx, focusRing, inputClass } from "@/components/ui";
import type { Job } from "@/lib/api";

import { NewJobForm } from "./new-job-form";

const FILTERS = [
  { key: "open", label: "Open" },
  { key: "to-validate", label: "To validate" },
  { key: "closed", label: "Closed" },
  { key: "all", label: "All" },
] as const;
type Filter = (typeof FILTERS)[number]["key"];

function keep(job: Job, filter: Filter): boolean {
  if (filter === "open") return job.status === "open";
  if (filter === "closed") return job.status !== "open";
  if (filter === "to-validate") return !job.requirements_validated;
  return true;
}

export function JobBoard({ jobs, startWithForm }: { jobs: Job[]; startWithForm: boolean }) {
  const [showForm, setShowForm] = useState(startWithForm);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("open");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs
      .filter((job) => keep(job, filter))
      .filter(
        (job) =>
          !q ||
          [job.profile.title, job.profile.company, job.profile.location?.city, ...(job.profile.skill_requirements ?? []).map((s) => s.name)]
            .join(" ")
            .toLowerCase()
            .includes(q),
      );
  }, [jobs, query, filter]);

  return (
    <div className="space-y-4">
      {showForm ? (
        <Card
          title="New job"
          description="Paste the full job description. The requirements are extracted, then you review and validate them."
          actions={
            jobs.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setShowForm(false)} icon={<X className="size-4" />}>
                Close
              </Button>
            )
          }
        >
          <NewJobForm />
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title, city, skill…"
            aria-label="Search jobs"
            className={cx(inputClass, "pl-8")}
          />
        </div>
        <div role="tablist" aria-label="Filter jobs" className="flex rounded-lg border border-zinc-200 bg-white p-0.5 dark:border-zinc-800 dark:bg-zinc-900">
          {FILTERS.map(({ key, label }) => {
            const count = jobs.filter((job) => keep(job, key)).length;
            return (
              <button
                key={key}
                role="tab"
                aria-selected={filter === key}
                onClick={() => setFilter(key)}
                className={cx(
                  "rounded-md px-2.5 py-1 text-xs font-medium",
                  filter === key ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300" : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100",
                  focusRing,
                )}
              >
                {label} <span className="tabular-nums opacity-70">{count}</span>
              </button>
            );
          })}
        </div>
        {!showForm && (
          <Button className="ml-auto" onClick={() => setShowForm(true)} icon={<Plus className="size-4" />}>
            New job
          </Button>
        )}
      </div>

      {visible.length === 0 ? (
        <Card>
          <Empty icon={<Briefcase />} title={jobs.length ? "No job matches" : "No job yet"}>
            {jobs.length ? "Change the search or the filter." : "Paste a job description above to create the first one."}
          </Empty>
        </Card>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((job) => {
            const skills = job.profile.skill_requirements ?? [];
            const required = skills.filter((s) => s.requirement === "required");
            return (
              <li key={job.id}>
                <Link
                  href={`/jobs/${job.id}`}
                  className={cx(
                    "flex h-full flex-col rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-indigo-700",
                    focusRing,
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h2 className="font-semibold leading-snug">{job.profile.title}</h2>
                    <Badge tone={job.status === "open" ? "blue" : "neutral"}>{job.status}</Badge>
                  </div>
                  <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-zinc-500">
                    {job.profile.company && <span>{job.profile.company}</span>}
                    {job.profile.location?.city && (
                      <span className="flex items-center gap-0.5">
                        <MapPin className="size-3" aria-hidden />
                        {job.profile.location.city}
                      </span>
                    )}
                    {job.profile.work_mode && <span>{job.profile.work_mode.replace("_", "-")}</span>}
                    {job.profile.contract_type && <span>{job.profile.contract_type.replace("_", " ")}</span>}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {required.slice(0, 5).map((s) => (
                      <Badge key={s.name}>{s.name}</Badge>
                    ))}
                    {required.length > 5 && <Badge>+{required.length - 5}</Badge>}
                  </div>
                  <div className="mt-auto flex items-center justify-between pt-4 text-xs text-zinc-500">
                    <span>
                      {required.length} required · {skills.length - required.length} preferred
                    </span>
                    {job.requirements_validated ? <Badge tone="green">validated</Badge> : <Badge tone="amber">to validate</Badge>}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
