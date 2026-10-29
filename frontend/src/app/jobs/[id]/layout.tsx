import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui";
import { api } from "@/lib/api";

import { JobStatusToggle } from "./job-status-toggle";
import { JobTabs } from "./tabs";

export async function generateMetadata(props: LayoutProps<"/jobs/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const job = await api.job(id);
  return { title: job.profile.title };
}

export default async function JobLayout(props: LayoutProps<"/jobs/[id]">) {
  const { id } = await props.params;
  const job = await api.job(id);
  const { profile } = job;
  const facts = [profile.company, profile.location?.city, profile.work_mode?.replace("_", "-"), profile.contract_type]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/jobs" className="text-xs text-zinc-500 hover:underline">
            ← Jobs
          </Link>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            {profile.title}
            <Badge tone={job.status === "open" ? "blue" : "neutral"}>{job.status}</Badge>
            {!job.requirements_validated && <Badge tone="amber">requirements not validated</Badge>}
          </h1>
          {facts && <p className="text-sm text-zinc-500">{facts}</p>}
        </div>
        <JobStatusToggle jobId={job.id} status={job.status === "closed" ? "closed" : "open"} />
      </div>
      <JobTabs jobId={job.id} />
      {props.children}
    </div>
  );
}
