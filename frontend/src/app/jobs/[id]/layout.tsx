import type { Metadata } from "next";

import { Badge, PageHeader } from "@/components/ui";
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
  const facts = [profile.company, profile.location?.city, profile.work_mode?.replace("_", "-"), profile.contract_type?.replace("_", " ")]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-5">
      <PageHeader
        crumbs={[{ label: "Jobs", href: "/jobs" }, { label: profile.title }]}
        title={profile.title}
        badges={
          <>
            <Badge tone={job.status === "open" ? "blue" : "neutral"}>{job.status}</Badge>
            {!job.requirements_validated && <Badge tone="amber">requirements not validated</Badge>}
          </>
        }
        description={facts || undefined}
        actions={<JobStatusToggle jobId={job.id} status={job.status === "closed" ? "closed" : "open"} />}
      />
      <JobTabs jobId={job.id} needsValidation={!job.requirements_validated} />
      {props.children}
    </div>
  );
}
