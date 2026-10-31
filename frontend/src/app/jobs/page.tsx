import type { Metadata } from "next";

import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

import { JobBoard } from "./job-board";

export const metadata: Metadata = { title: "Jobs" };

export default async function JobsPage(props: PageProps<"/jobs">) {
  const [jobs, params] = await Promise.all([api.jobs(), props.searchParams]);

  return (
    <div className="space-y-6">
      <PageHeader title="Jobs" description="Each job ranks the whole talent pool against its validated requirements." />
      <JobBoard jobs={jobs} startWithForm={params.new === "1" || jobs.length === 0} />
    </div>
  );
}
