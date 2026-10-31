import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Briefcase, ClipboardCheck, FileUp, KanbanSquare, MessageSquare, ShieldAlert, Users } from "lucide-react";

import { Badge, ButtonLink, Card, Empty, PageHeader, Stat, cx, focusRing } from "@/components/ui";
import { api, type Application, type Candidate, type Job } from "@/lib/api";
import { STAGES, STAGE_LABELS } from "@/lib/enums";
import { actionLabel, timeAgo } from "@/lib/format";

export const metadata: Metadata = { title: "Dashboard" };

const SECURITY_FLAGS = new Set(["hidden_text", "possible_prompt_injection"]);

const STAGE_COLORS: Record<string, string> = {
  new: "bg-zinc-400",
  screening: "bg-sky-500",
  interview: "bg-indigo-500",
  offer: "bg-violet-500",
  hired: "bg-emerald-500",
  rejected: "bg-red-400",
  withdrawn: "bg-zinc-300",
};

type Task = { key: string; icon: ReactNode; tone: string; title: string; detail: string; href: string };

function tasks(jobs: Job[], candidates: Candidate[], pipelines: Map<string, Application[]>): Task[] {
  const list: Task[] = [];
  for (const job of jobs.filter((j) => j.status === "open" && !j.requirements_validated)) {
    list.push({
      key: `validate-${job.id}`,
      icon: <ClipboardCheck />,
      tone: "text-amber-600",
      title: `Validate the requirements of ${job.profile.title}`,
      detail: "Rankings use unvalidated requirements until you review them.",
      href: `/jobs/${job.id}/requirements`,
    });
  }
  for (const candidate of candidates) {
    const flags = (candidate.extraction.document_flags as string[] | undefined) ?? [];
    const name = candidate.profile.identity?.full_name ?? "Unnamed candidate";
    if (flags.some((f) => SECURITY_FLAGS.has(f))) {
      list.push({
        key: `flag-${candidate.id}`,
        icon: <ShieldAlert />,
        tone: "text-red-600",
        title: `Check ${name}'s document`,
        detail: "Hidden text or text addressed to an AI was found in the file.",
        href: `/candidates/${candidate.id}`,
      });
    }
    const unverified = (candidate.extraction.evidence as { unverified?: number } | undefined)?.unverified ?? 0;
    if (unverified > 0) {
      list.push({
        key: `verify-${candidate.id}`,
        icon: <AlertTriangle />,
        tone: "text-amber-600",
        title: `Review ${unverified} unverified item${unverified > 1 ? "s" : ""} for ${name}`,
        detail: "They earn no credit in matching until you confirm them.",
        href: `/candidates/${candidate.id}`,
      });
    }
  }
  for (const job of jobs) {
    const waiting = (pipelines.get(job.id) ?? []).filter((a) => a.stage === "new").length;
    if (waiting > 0) {
      list.push({
        key: `screen-${job.id}`,
        icon: <KanbanSquare />,
        tone: "text-indigo-600",
        title: `Screen ${waiting} new application${waiting > 1 ? "s" : ""} for ${job.profile.title}`,
        detail: "They are waiting in the first stage of the pipeline.",
        href: `/jobs/${job.id}/pipeline`,
      });
    }
  }
  return list;
}

export default async function DashboardPage() {
  const [jobs, candidates, activity] = await Promise.all([api.jobs(), api.candidates(), api.audit({ limit: "8" })]);
  const openJobs = jobs.filter((j) => j.status === "open");
  const pipelines = new Map(
    await Promise.all(openJobs.map(async (job) => [job.id, await api.applications(job.id, false)] as const)),
  );
  const todo = tasks(jobs, candidates, pipelines);
  const active = [...pipelines.values()].flat().filter((a) => !["hired", "rejected", "withdrawn"].includes(a.stage));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="What needs your attention today."
        actions={
          <>
            <ButtonLink href="/candidates?upload=1" icon={<FileUp className="size-4" />}>
              Upload CVs
            </ButtonLink>
            <ButtonLink href="/jobs?new=1" variant="primary" icon={<Briefcase className="size-4" />}>
              New job
            </ButtonLink>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Open jobs" value={openJobs.length} hint={`${jobs.length - openJobs.length} closed`} icon={<Briefcase />} href="/jobs" />
        <Stat label="Candidates" value={candidates.length} hint="in the talent pool" icon={<Users />} href="/candidates" />
        <Stat label="Active applications" value={active.length} hint="across open jobs" icon={<KanbanSquare />} />
        <Stat label="To do" value={todo.length} hint={todo.length ? "see below" : "all clear"} icon={<ClipboardCheck />} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <Card title="Needs your attention" flush>
            {todo.length === 0 ? (
              <Empty icon={<ClipboardCheck />} title="Nothing to review">
                Requirements are validated, documents are clean and no application is waiting.
              </Empty>
            ) : (
              <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {todo.map((task) => (
                  <li key={task.key}>
                    <Link
                      href={task.href}
                      className={cx("group flex items-start gap-3 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50", focusRing)}
                    >
                      <span className={cx("mt-0.5 [&>svg]:size-4", task.tone)}>{task.icon}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium">{task.title}</span>
                        <span className="block text-xs text-zinc-500">{task.detail}</span>
                      </span>
                      <ArrowRight className="mt-0.5 size-4 text-zinc-300 transition-transform group-hover:translate-x-0.5 group-hover:text-zinc-500" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Pipelines" description="Applications per stage for each open job.">
            {openJobs.length === 0 ? (
              <Empty icon={<Briefcase />} title="No open job" action={<ButtonLink href="/jobs?new=1">Create a job</ButtonLink>} />
            ) : (
              <ul className="space-y-4">
                {openJobs.map((job) => {
                  const apps = pipelines.get(job.id) ?? [];
                  return (
                    <li key={job.id}>
                      <div className="mb-1.5 flex items-center justify-between gap-2 text-sm">
                        <Link href={`/jobs/${job.id}/pipeline`} className={cx("rounded font-medium hover:underline", focusRing)}>
                          {job.profile.title}
                        </Link>
                        <span className="text-xs text-zinc-500">{apps.length} in pipeline</span>
                      </div>
                      {apps.length === 0 ? (
                        <div className="flex items-center justify-between rounded-md border border-dashed border-zinc-300 px-3 py-2 text-xs text-zinc-500 dark:border-zinc-700">
                          Nobody yet.
                          <Link href={`/jobs/${job.id}`} className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                            See the ranking
                          </Link>
                        </div>
                      ) : (
                        <>
                          <div className="flex h-2.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                            {STAGES.map((stage) => {
                              const count = apps.filter((a) => a.stage === stage).length;
                              return count ? (
                                <div
                                  key={stage}
                                  className={STAGE_COLORS[stage]}
                                  style={{ width: `${(count / apps.length) * 100}%` }}
                                  title={`${STAGE_LABELS[stage]}: ${count}`}
                                />
                              ) : null;
                            })}
                          </div>
                          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-zinc-500">
                            {STAGES.map((stage) => {
                              const count = apps.filter((a) => a.stage === stage).length;
                              return count ? (
                                <span key={stage} className="flex items-center gap-1">
                                  <span className={cx("size-2 rounded-full", STAGE_COLORS[stage])} />
                                  {STAGE_LABELS[stage]} {count}
                                </span>
                              ) : null;
                            })}
                          </div>
                        </>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Ask the assistant">
            <p className="text-sm text-zinc-500">Rank, compare, explain or draft emails in plain language, in English or French.</p>
            <ButtonLink href="/assistant" className="mt-3 w-full" icon={<MessageSquare className="size-4" />}>
              Open the assistant
            </ButtonLink>
          </Card>
          <Card title="Recent activity" actions={<Link href="/audit" className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400">Audit log</Link>} flush>
            {activity.length === 0 ? (
              <Empty>No activity yet.</Empty>
            ) : (
              <ol className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {activity.map((entry) => (
                  <li key={entry.id} className="flex items-center justify-between gap-2 px-4 py-2.5 text-sm">
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{actionLabel(entry.action)}</span>
                      <span className="block text-xs text-zinc-500">by {entry.actor}</span>
                    </span>
                    <Badge>{timeAgo(entry.created_at)}</Badge>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
