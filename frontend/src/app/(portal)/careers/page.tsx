import type { Metadata } from "next";
import Link from "next/link";
import { Briefcase, CheckCircle2, MapPin, Search } from "lucide-react";

import { CompanyMark, JobIcon } from "@/components/job-visuals";
import { Badge, Button, Empty, Notice, cx, inputClass, selectClass } from "@/components/ui";
import { api, type PublicJob } from "@/lib/api";
import { CONTRACT_TYPES, WORK_MODES } from "@/lib/enums";
import { humanize, timeAgo } from "@/lib/format";
import { currentUser } from "@/lib/session";

export const metadata: Metadata = { title: "Find a job" };

function JobCard({ job, applied }: { job: PublicJob; applied: boolean }) {
  const facts = [job.city, humanize(job.work_mode), humanize(job.contract_type)].filter(Boolean);
  return (
    <Link
      href={`/careers/${job.id}`}
      className="group flex min-w-0 flex-col rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-brand-700"
    >
      <div className="flex items-start gap-3">
        <JobIcon title={job.title} />
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-semibold group-hover:text-brand-700 dark:group-hover:text-brand-300">{job.title}</h2>
          <div className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-300">
            <CompanyMark name={job.company.name} />
          </div>
        </div>
        {applied && (
          <Badge tone="green">
            <CheckCircle2 className="size-3" aria-hidden /> Applied
          </Badge>
        )}
      </div>
      {facts.length > 0 && (
        <p className="mt-3 flex items-center gap-1 text-xs text-zinc-500">
          <MapPin className="size-3.5" aria-hidden /> {facts.join(" · ")}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-1">
        {job.required_skills.slice(0, 4).map((skill) => (
          <Badge key={skill}>{skill}</Badge>
        ))}
        {job.required_skills.length > 4 && <Badge tone="indigo">+{job.required_skills.length - 4}</Badge>}
      </div>
      <p className="mt-auto pt-4 text-xs text-zinc-500">Posted {timeAgo(job.posted_at)}</p>
    </Link>
  );
}

export default async function CareersPage({ searchParams }: PageProps<"/careers">) {
  const params = await searchParams;
  const pick = (key: string) => (typeof params[key] === "string" && params[key] ? (params[key] as string) : undefined);
  const filters = { q: pick("q"), work_mode: pick("work_mode"), contract_type: pick("contract_type") };
  const [jobs, user] = await Promise.all([api.publicJobs(filters), currentUser()]);
  const company = pick("company");
  const shown = company ? jobs.filter((job) => job.company.id === company) : jobs;
  const applied = new Set(user?.role === "candidate" ? (await api.myApplications()).map((a) => a.job.id) : []);
  const filtered = Object.values(filters).some(Boolean) || company;

  return (
    <div className="space-y-8">
      {params.deleted && <Notice tone="green">Your account and all your data have been deleted.</Notice>}
      <section className="relative overflow-hidden rounded-2xl bg-navy-950 px-6 py-10 text-white sm:px-10">
        <div className="pointer-events-none absolute -right-20 -top-28 size-80 rounded-full bg-brand-600/30 blur-3xl" aria-hidden />
        <div className="relative max-w-2xl">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Find your next role</h1>
          <p className="mt-2 text-slate-300">
            Apply in a minute with your CV. You stay in control of your data, and every decision about you is made by a person.
          </p>
          <form action="/careers" className="mt-6 flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
              <input name="q" defaultValue={filters.q} placeholder="Job title, skill, company or city" aria-label="Search jobs" className={cx(inputClass, "h-11 pl-9 text-zinc-900")} />
            </div>
            <select name="work_mode" defaultValue={filters.work_mode ?? ""} aria-label="Work mode" className={cx(selectClass, "h-11 text-zinc-900 sm:w-44")}>
              <option value="">Any work mode</option>
              {WORK_MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {humanize(mode)}
                </option>
              ))}
            </select>
            <select name="contract_type" defaultValue={filters.contract_type ?? ""} aria-label="Contract" className={cx(selectClass, "h-11 text-zinc-900 sm:w-40")}>
              <option value="">Any contract</option>
              {CONTRACT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {humanize(type)}
                </option>
              ))}
            </select>
            <Button type="submit" className="h-11 px-5">
              Search
            </Button>
          </form>
        </div>
      </section>

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-600 dark:text-zinc-300">
          {shown.length} open position{shown.length === 1 ? "" : "s"}
          {company && shown[0] && ` at ${shown[0].company.name}`}
        </h2>
        {filtered && (
          <Link href="/careers" className="text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">
            Clear filters
          </Link>
        )}
      </div>

      {shown.length === 0 ? (
        <Empty icon={<Briefcase />} title={filtered ? "No job matches your search" : "No open position right now"}>
          {filtered ? "Try other words or fewer filters." : "Come back soon: companies post new roles regularly."}
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((job) => (
            <JobCard key={job.id} job={job} applied={applied.has(job.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
