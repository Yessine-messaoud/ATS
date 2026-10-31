import type { Metadata } from "next";
import { Briefcase, ClipboardList, Hourglass, UserCheck } from "lucide-react";

import { Card, PageHeader, Stat } from "@/components/ui";
import { loadWorkspace } from "@/lib/api";
import { SHORTLIST_STAGES, kpis } from "@/lib/insights";

import { CreateJobButton } from "./create-job-button";
import { JobsTable, type JobRow } from "./jobs-table";

export const metadata: Metadata = { title: "Jobs" };

export default async function JobsPage(props: PageProps<"/jobs">) {
  const [{ jobs, applications }, params] = await Promise.all([loadWorkspace(), props.searchParams]);
  const numbers = kpis(jobs, applications);
  const rows: JobRow[] = jobs.map((job) => {
    const mine = applications.filter((a) => a.job_id === job.id);
    return { job, applications: mine.length, shortlisted: mine.filter((a) => SHORTLIST_STAGES.has(a.stage)).length };
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description="Each job ranks the talent pool against its validated requirements."
        actions={<CreateJobButton startOpen={params.new === "1" || jobs.length === 0} />}
      />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Active jobs" value={numbers.activeJobs} hint={`${numbers.closedJobs} closed`} icon={<Briefcase />} />
        <Stat label="Total applications" value={numbers.applications} hint={`${numbers.activeApplications} in progress`} icon={<ClipboardList />} />
        <Stat label="Candidates shortlisted" value={numbers.shortlisted} hint="interview stage or later" icon={<UserCheck />} />
        <Stat label="Pending CV evaluations" value={numbers.pendingEvaluations} hint="applications not screened yet" icon={<Hourglass />} href="/evaluations" />
      </div>
      <Card flush title="All jobs" description="Search, filter and sort; open a job for its ranking, requirements and pipeline.">
        <JobsTable rows={rows} />
      </Card>
    </div>
  );
}
