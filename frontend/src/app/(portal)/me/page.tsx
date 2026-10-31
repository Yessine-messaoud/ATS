import type { Metadata } from "next";
import Link from "next/link";
import { Briefcase, CircleCheck, FileText, Loader2, Search, TriangleAlert, UserRound } from "lucide-react";

import { JobIcon } from "@/components/job-visuals";
import { Badge, ButtonLink, Card, Empty, Notice, PageHeader, Stat, cx } from "@/components/ui";
import { api, type CvTask, type PortalApplication } from "@/lib/api";
import { formatDate, timeAgo } from "@/lib/format";
import { currentUser } from "@/lib/session";

import { AutoRefresh, WithdrawButton } from "./application-actions";

export const metadata: Metadata = { title: "My applications" };

const STEPS = [
  { key: "received", label: "Received" },
  { key: "in_review", label: "In review" },
  { key: "interview", label: "Interview" },
  { key: "offer", label: "Offer" },
];
const OUTCOME = {
  hired: { tone: "green", label: "Hired", text: "Congratulations! The company will contact you about the next steps." },
  not_selected: { tone: "neutral", label: "Not selected", text: "The company decided not to move forward. Thank you for applying." },
  withdrawn: { tone: "neutral", label: "Withdrawn", text: "You withdrew this application." },
} as const;

function Progress({ status }: { status: string }) {
  const reached = STEPS.findIndex((s) => s.key === status);
  return (
    <ol className="flex items-center gap-1" aria-label="Application progress">
      {STEPS.map((step, index) => {
        const done = index <= reached;
        return (
          <li key={step.key} className="flex min-w-0 flex-1 flex-col gap-1">
            <span className={cx("h-1.5 rounded-full", done ? "bg-brand-500" : "bg-zinc-200 dark:bg-zinc-800")} />
            <span className={cx("truncate text-[11px]", index === reached ? "font-medium text-brand-700 dark:text-brand-300" : "text-zinc-500")} aria-current={index === reached ? "step" : undefined}>
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function ApplicationCard({ application }: { application: PortalApplication }) {
  const outcome = OUTCOME[application.status as keyof typeof OUTCOME];
  return (
    <li className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
      <Link href={`/careers/${application.job.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <JobIcon title={application.job.title} />
        <span className="min-w-0">
          <span className="block truncate font-medium hover:underline">{application.job.title}</span>
          <span className="block truncate text-sm text-zinc-500">
            {application.job.company.name} · applied {formatDate(application.applied_at)}
          </span>
        </span>
      </Link>
      <div className="w-full sm:w-72">
        {outcome ? (
          <div className="text-sm">
            <Badge tone={outcome.tone}>{outcome.label}</Badge>
            <p className="mt-1 text-xs text-zinc-500">{outcome.text}</p>
          </div>
        ) : (
          <Progress status={application.status} />
        )}
      </div>
      <div className="flex items-center justify-between gap-3 sm:w-36 sm:flex-col sm:items-end">
        <span className="text-xs text-zinc-500">Updated {timeAgo(application.updated_at)}</span>
        {application.can_withdraw && <WithdrawButton id={application.id} title={application.job.title} />}
      </div>
    </li>
  );
}

function TaskRow({ task }: { task: CvTask }) {
  const busy = task.status === "queued" || task.status === "processing";
  return (
    <li className="flex items-start gap-3 px-4 py-3 text-sm">
      {busy ? <Loader2 className="mt-0.5 size-4 animate-spin text-brand-600" aria-hidden /> : <TriangleAlert className="mt-0.5 size-4 text-red-500" aria-hidden />}
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{busy ? `Reading ${task.filename ?? "your CV"}…` : `We could not use ${task.filename ?? "your CV"}`}</span>
        <span className="block text-xs text-zinc-500">{busy ? "Your application is created as soon as it is read, usually within a minute or two." : task.error}</span>
      </span>
      <span className="whitespace-nowrap text-xs text-zinc-500">{timeAgo(task.created_at)}</span>
    </li>
  );
}

export default async function MyApplicationsPage({ searchParams }: PageProps<"/me">) {
  const params = await searchParams;
  const [user, applications, tasks, profile] = await Promise.all([currentUser(), api.myApplications(), api.myTasks(), api.myProfile()]);
  // CVs being read, and failures not yet followed by a CV that was read successfully (tasks come newest first).
  const lastDone = tasks.findIndex((t) => t.status === "done");
  const recent = tasks.filter((t, i) => t.status === "queued" || t.status === "processing" || (t.status === "failed" && (lastDone === -1 || i < lastDone)));
  const processing = recent.some((t) => t.status !== "failed");
  const open = applications.filter((a) => a.can_withdraw);

  return (
    <div className="space-y-6">
      {processing && <AutoRefresh />}
      <PageHeader
        title={`Hello, ${user?.full_name.split(" ")[0] ?? "there"}`}
        description="Follow your applications. Companies update their status as they review them."
        actions={
          <ButtonLink href="/careers" icon={<Search className="size-4" />} variant="primary">
            Find jobs
          </ButtonLink>
        }
      />
      {params.applied === "processing" && processing && <Notice tone="blue">Application sent. We are reading your CV; it will appear below in a minute or two.</Notice>}
      {params.applied === "done" && <Notice tone="green">Application sent with your current profile.</Notice>}

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Open applications" value={open.length} icon={<Briefcase />} />
        <Stat label="Interviews" value={applications.filter((a) => a.status === "interview" || a.status === "offer").length} icon={<CircleCheck />} />
        <Stat
          label="My profile"
          value={profile ? "Ready" : "No CV yet"}
          hint={profile && profile.unverified_items > 0 ? `${profile.unverified_items} item(s) to check` : profile ? "Check what was read from your CV" : "Apply to a job to send your CV"}
          icon={<UserRound />}
          href="/me/profile"
        />
      </div>

      {recent.length > 0 && (
        <Card flush title="Your CVs">
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {recent.map((task) => (
              <TaskRow key={task.id} task={task} />
            ))}
          </ul>
        </Card>
      )}

      <Card flush title="Applications" description={`${applications.length} in total`}>
        {applications.length === 0 ? (
          <Empty icon={<FileText />} title="No application yet">
            <Link href="/careers" className="font-medium text-brand-700 hover:underline dark:text-brand-300">
              Browse open jobs
            </Link>{" "}
            and apply with your CV in a minute.
          </Empty>
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {applications.map((application) => (
              <ApplicationCard key={application.id} application={application} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
