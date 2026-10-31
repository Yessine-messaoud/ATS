import type { Metadata } from "next";
import Link from "next/link";
import { Activity, Briefcase, Building2, CheckCircle2, Cpu, FileClock, Lock, TriangleAlert, Users } from "lucide-react";

import { Badge, Card, Empty, Notice, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { actionLabel, actorLabel, timeAgo } from "@/lib/format";
import { requireUser } from "@/lib/session";

import { CompanyActions } from "./companies/company-actions";

export const metadata: Metadata = { title: "Administration" };

const TASK_TONE = { queued: "blue", processing: "indigo", done: "green", failed: "red" } as const;

export default async function AdminOverviewPage() {
  await requireUser(["admin"], "/admin");
  const [overview, pending, tasks, activity] = await Promise.all([
    api.adminOverview(),
    api.adminOrganizations("pending"),
    api.adminTasks(),
    api.audit({ limit: "8" }),
  ]);
  const count = (map: Record<string, number>, key: string) => map[key] ?? 0;
  const n = (value: number, word: string) => `${value} ${word}${value === 1 ? "" : "s"}`;

  return (
    <div className="space-y-6">
      <PageHeader title="Platform overview" description="Companies, accounts and the health of the platform." />

      {overview.production_problems.length > 0 && (
        <Notice tone="amber" icon={<TriangleAlert />}>
          Not ready for real candidate data: {overview.production_problems.join("; ")}.
        </Notice>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Companies"
          value={count(overview.organizations, "active")}
          hint={`${count(overview.organizations, "pending")} awaiting approval · ${count(overview.organizations, "suspended")} suspended`}
          icon={<Building2 />}
          href="/admin/companies"
        />
        <Stat
          label="Accounts"
          value={Object.values(overview.users).reduce((a, b) => a + b, 0)}
          hint={`${n(count(overview.users, "recruiter"), "recruiter")} · ${n(count(overview.users, "candidate"), "candidate")} · ${n(count(overview.users, "admin"), "admin")}`}
          icon={<Users />}
          href="/admin/users"
        />
        <Stat label="Open jobs" value={overview.open_jobs} hint={`${n(overview.jobs, "job")} in total`} icon={<Briefcase />} />
        <Stat
          label="Applications"
          value={overview.applications}
          hint={`${n(overview.candidates, "candidate")}, ${overview.portal_candidates} through the job board`}
          icon={<Activity />}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card flush title="Companies awaiting approval" description="Their jobs are hidden from the job board until approved." actions={<Link href="/admin/companies" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">All companies</Link>}>
          {pending.length === 0 ? (
            <Empty icon={<CheckCircle2 />} title="Nothing to review">New company sign-ups appear here.</Empty>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {pending.map((organization) => (
                <li key={organization.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{organization.name}</span>
                    <span className="block text-xs text-zinc-500">
                      Signed up {timeAgo(organization.created_at)} · {organization.recruiters} recruiter{organization.recruiters === 1 ? "" : "s"} · {organization.jobs} job
                      {organization.jobs === 1 ? "" : "s"} prepared
                    </span>
                  </span>
                  <CompanyActions organization={organization} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="System">
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt className="flex items-center gap-2 text-zinc-500">
                <Cpu className="size-4" aria-hidden /> AI model
              </dt>
              <dd className="truncate font-medium">{overview.llm_model}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="flex items-center gap-2 text-zinc-500">
                <Lock className="size-4" aria-hidden /> Documents encrypted at rest
              </dt>
              <dd>{overview.document_encryption ? <Badge tone="green">on</Badge> : <Badge tone="red">off</Badge>}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="flex items-center gap-2 text-zinc-500">
                <FileClock className="size-4" aria-hidden /> CVs being read
              </dt>
              <dd className="flex gap-1">
                {(["queued", "processing", "failed"] as const).map((status) => (
                  <Badge key={status} tone={TASK_TONE[status]}>
                    {count(overview.tasks, status)} {status}
                  </Badge>
                ))}
              </dd>
            </div>
          </dl>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card flush title="Recent CV processing" description="Applications sent through the job board are read in the background.">
          {tasks.length === 0 ? (
            <Empty>No CV received through the job board yet.</Empty>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {tasks.slice(0, 8).map((task) => (
                <li key={task.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <Badge tone={TASK_TONE[task.status]}>{task.status}</Badge>
                  <span className="min-w-0 flex-1 truncate">{task.filename ?? "CV"}</span>
                  {task.error && <span className="hidden max-w-[16rem] truncate text-xs text-red-600 sm:block dark:text-red-400">{task.error}</span>}
                  <span className="whitespace-nowrap text-xs text-zinc-500">{timeAgo(task.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card flush title="Latest activity" actions={<Link href="/audit" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">Audit log</Link>}>
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {activity.map((entry) => (
              <li key={entry.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                <span className="min-w-0 truncate">
                  {actionLabel(entry.action)} <span className="text-zinc-500">by {actorLabel(entry)}</span>
                </span>
                <span className="whitespace-nowrap text-xs text-zinc-500">{timeAgo(entry.created_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
