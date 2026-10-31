import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { ArrowRight, Briefcase, ClipboardCheck, ClipboardList, FileUp, Hourglass, KanbanSquare, ShieldAlert, TriangleAlert, UserCheck } from "lucide-react";

import { ChartCard, DonutChart, TrendChart } from "@/components/charts";
import { Badge, ButtonLink, Card, Empty, PageHeader, Stat, cx, focusRing } from "@/components/ui";
import { applicationsOverTime, parseRange, pipelineBreakdown } from "@/lib/analytics";
import { api, loadWorkspace } from "@/lib/api";
import { actionLabel, timeAgo, actorLabel } from "@/lib/format";
import { SHORTLIST_STAGES, kpis, tasks, type Task } from "@/lib/insights";
import { currentUser } from "@/lib/session";

import { CreateJobButton } from "./jobs/create-job-button";
import { JobsTable, type JobRow } from "./jobs/jobs-table";

export const metadata: Metadata = { title: "Dashboard" };

const TASK_ICONS: Record<Task["kind"], ReactNode> = {
  validate: <ClipboardCheck className="text-amber-500" />,
  security: <ShieldAlert className="text-red-500" />,
  verify: <TriangleAlert className="text-amber-500" />,
  screen: <KanbanSquare className="text-brand-500" />,
};

export default async function DashboardPage() {
  if ((await currentUser())?.role === "admin") redirect("/admin");
  const [{ jobs, candidates, applications }, activity] = await Promise.all([loadWorkspace(), api.audit({ limit: "6" })]);
  const numbers = kpis(jobs, applications);
  const todo = tasks(jobs, candidates, applications);
  const trend = applicationsOverTime(applications, parseRange({ range: "30" }));
  const rows: JobRow[] = jobs
    .filter((job) => job.status === "open")
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 5)
    .map((job) => {
      const mine = applications.filter((a) => a.job_id === job.id);
      return { job, applications: mine.length, shortlisted: mine.filter((a) => SHORTLIST_STAGES.has(a.stage)).length };
    });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Your recruitment at a glance, and what needs your attention."
        actions={
          <>
            <ButtonLink href="/candidates?upload=1" icon={<FileUp className="size-4" />}>
              Upload CVs
            </ButtonLink>
            <CreateJobButton />
          </>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Active jobs" value={numbers.activeJobs} hint={`${numbers.closedJobs} closed`} icon={<Briefcase />} href="/jobs" />
        <Stat label="Total applications" value={numbers.applications} hint={`${numbers.activeApplications} in progress`} icon={<ClipboardList />} href="/analytics" />
        <Stat label="Candidates shortlisted" value={numbers.shortlisted} hint="interview stage or later" icon={<UserCheck />} />
        <Stat label="Pending CV evaluations" value={numbers.pendingEvaluations} hint="applications not screened yet" icon={<Hourglass />} href="/evaluations" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <ChartCard
          title="Applications over time"
          description="Last 30 days"
          className="xl:col-span-2"
          actions={
            <Link href="/analytics" className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-400">
              Analytics →
            </Link>
          }
        >
          <TrendChart data={trend.series} height={200} />
        </ChartCard>
        <ChartCard title="Candidate pipeline" description="All applications by stage">
          <DonutChart data={pipelineBreakdown(applications)} centerLabel="applications" />
        </ChartCard>
      </div>

      <Card
        flush
        title="Open jobs"
        description="Most recent first"
        actions={
          <Link href="/jobs" className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-400">
            All jobs →
          </Link>
        }
      >
        <JobsTable rows={rows} compact />
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <Card title="Needs your attention" description={todo.length ? `${todo.length} item${todo.length === 1 ? "" : "s"}` : undefined} flush>
          {todo.length === 0 ? (
            <Empty icon={<ClipboardCheck />} title="Nothing to review">
              Requirements are validated, documents are clean and no application is waiting.
            </Empty>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {todo.map((task) => (
                <li key={task.key}>
                  <Link href={task.href} className={cx("group flex items-start gap-3 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50", focusRing)}>
                    <span className="mt-0.5 [&>svg]:size-4">{TASK_ICONS[task.kind]}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{task.title}</span>
                      <span className="block text-xs text-zinc-500">{task.detail}</span>
                    </span>
                    <ArrowRight className="mt-0.5 size-4 text-zinc-300 transition-transform group-hover:translate-x-0.5 group-hover:text-zinc-500" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card
          title="Recent activity"
          flush
          actions={
            <Link href="/audit" className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-400">
              Audit log →
            </Link>
          }
        >
          {activity.length === 0 ? (
            <Empty>No activity yet.</Empty>
          ) : (
            <ol className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {activity.map((entry) => (
                <li key={entry.id} className="flex items-center justify-between gap-2 px-4 py-2.5 text-sm">
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{actionLabel(entry.action)}</span>
                    <span className="block text-xs text-zinc-500">by {actorLabel(entry)}</span>
                  </span>
                  <Badge>{timeAgo(entry.created_at)}</Badge>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}
