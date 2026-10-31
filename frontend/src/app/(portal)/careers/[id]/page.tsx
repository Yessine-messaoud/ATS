import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Building2, CalendarDays, CheckCircle2, ExternalLink, Globe2, Languages, MapPin } from "lucide-react";

import { CompanyMark, JobIcon } from "@/components/job-visuals";
import { Badge, Card, buttonClass, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, humanize } from "@/lib/format";
import { currentUser } from "@/lib/session";

import { ApplyForm } from "./apply-form";

export async function generateMetadata({ params }: PageProps<"/careers/[id]">): Promise<Metadata> {
  const job = await api.publicJob((await params).id);
  return { title: job ? `${job.title} · ${job.company.name}` : "Job not found" };
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold">{title}</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-700 dark:text-zinc-300">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export default async function JobDetailPage({ params }: PageProps<"/careers/[id]">) {
  const { id } = await params;
  const [job, user] = await Promise.all([api.publicJob(id), currentUser()]);
  if (!job) notFound();
  const candidate = user?.role === "candidate";
  const [applications, profile] = candidate ? await Promise.all([api.myApplications(), api.myProfile()]) : [[], null];
  const application = applications.find((a) => a.job.id === job.id);
  const facts = [
    { icon: MapPin, text: [job.city, job.country].filter(Boolean).join(", ") || null },
    { icon: Building2, text: humanize(job.work_mode) },
    { icon: CalendarDays, text: humanize(job.contract_type) },
  ].filter((f) => f.text);

  return (
    <div className="space-y-6">
      <Link href="/careers" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
        <ArrowLeft className="size-4" aria-hidden /> All jobs
      </Link>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <header className="flex items-start gap-4">
            <JobIcon title={job.title} />
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight">{job.title}</h1>
              <div className="mt-1 text-zinc-600 dark:text-zinc-300">
                <CompanyMark name={job.company.name} />
              </div>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-500">
                {facts.map(({ icon: Icon, text }) => (
                  <span key={text} className="flex items-center gap-1">
                    <Icon className="size-4" aria-hidden /> {text}
                  </span>
                ))}
                {job.seniority && <span>{humanize(job.seniority)}</span>}
                {job.min_years_experience !== null && job.min_years_experience !== undefined && <span>{job.min_years_experience}+ years of experience</span>}
                <span>Posted {formatDate(job.posted_at)}</span>
              </div>
            </div>
          </header>

          <Card>
            <div className="space-y-6">
              {(job.required_skills.length > 0 || job.preferred_skills.length > 0) && (
                <section>
                  <h2 className="text-sm font-semibold">Skills</h2>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {job.required_skills.map((skill) => (
                      <Badge key={skill} tone="indigo">
                        {skill}
                      </Badge>
                    ))}
                    {job.preferred_skills.map((skill) => (
                      <Badge key={skill}>{skill} · nice to have</Badge>
                    ))}
                  </div>
                </section>
              )}
              <List title="What you will do" items={job.responsibilities} />
              {job.languages.length > 0 && (
                <p className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <Languages className="size-4 text-zinc-400" aria-hidden /> {job.languages.join(" · ")}
                </p>
              )}
              <List title="Benefits" items={job.benefits} />
              {job.description && (
                <section>
                  <h2 className="text-sm font-semibold">The job ad</h2>
                  <div className="mt-2 whitespace-pre-line text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{job.description}</div>
                </section>
              )}
            </div>
          </Card>

          <Card title={`About ${job.company.name}`}>
            <div className="space-y-3 text-sm">
              {job.company.description ? <p className="whitespace-pre-line text-zinc-700 dark:text-zinc-300">{job.company.description}</p> : <p className="text-zinc-500">The company has not written a description yet.</p>}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-zinc-500">
                {job.company.industry && <span>{job.company.industry}</span>}
                {job.company.size && <span>{job.company.size} employees</span>}
                {job.company.city && <span>{job.company.city}</span>}
                {job.company.website && (
                  <a href={job.company.website} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-brand-700 hover:underline dark:text-brand-300">
                    <Globe2 className="size-3.5" aria-hidden /> Website <ExternalLink className="size-3" aria-hidden />
                  </a>
                )}
              </div>
              <Link href={`/careers?company=${job.company.id}`} className="inline-block font-medium text-brand-700 hover:underline dark:text-brand-300">
                All jobs at {job.company.name}
              </Link>
            </div>
          </Card>
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <Card title="Apply for this job">
            {application ? (
              <div className="space-y-3 text-sm">
                <p className="flex items-center gap-2 font-medium text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="size-4" aria-hidden /> You applied on {formatDate(application.applied_at)}
                </p>
                <p className="text-zinc-600 dark:text-zinc-300">
                  Status: <Badge>{application.status_label}</Badge>
                </p>
                <Link href="/me" className={cx(buttonClass("secondary"), "w-full")}>
                  Follow my applications
                </Link>
              </div>
            ) : candidate ? (
              <ApplyForm jobId={job.id} profileFile={profile?.filename ?? (profile ? "your current CV" : null)} />
            ) : user ? (
              <p className="text-sm text-zinc-500">You are signed in with a {user.role} account. Candidates apply with a candidate account.</p>
            ) : (
              <div className="space-y-3 text-sm">
                <p className="text-zinc-600 dark:text-zinc-300">Create a free candidate account to apply and follow your application.</p>
                <Link href={`/signup?next=/careers/${job.id}`} className={cx(buttonClass("primary"), "w-full")}>
                  Create account and apply
                </Link>
                <Link href={`/login?next=/careers/${job.id}`} className={cx(buttonClass("secondary"), "w-full")}>
                  I already have an account
                </Link>
              </div>
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}
