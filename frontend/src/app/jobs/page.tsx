import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Card, Empty } from "@/components/ui";
import { api } from "@/lib/api";

import { NewJobForm } from "./new-job-form";

export const metadata: Metadata = { title: "Jobs" };

export default async function JobsPage() {
  const jobs = await api.jobs();

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <Card title={`Jobs (${jobs.length})`}>
        {jobs.length === 0 ? (
          <Empty>No jobs yet. Paste a job description to create the first one.</Empty>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="pb-2 font-medium">Title</th>
                <th className="pb-2 font-medium">Company</th>
                <th className="pb-2 font-medium">Requirements</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {jobs.map((job) => {
                const skills = job.profile.skill_requirements ?? [];
                const required = skills.filter((s) => s.requirement === "required").length;
                return (
                  <tr key={job.id}>
                    <td className="py-2">
                      <Link href={`/jobs/${job.id}`} className="font-medium hover:underline">
                        {job.profile.title}
                      </Link>
                    </td>
                    <td className="py-2 text-zinc-600 dark:text-zinc-400">{job.profile.company ?? "—"}</td>
                    <td className="py-2">
                      <span className="mr-2 text-zinc-600 dark:text-zinc-400">
                        {required} required · {skills.length - required} preferred
                      </span>
                      {job.requirements_validated ? (
                        <Badge tone="green">validated</Badge>
                      ) : (
                        <Badge tone="amber">to validate</Badge>
                      )}
                    </td>
                    <td className="py-2">
                      <Badge tone={job.status === "open" ? "blue" : "neutral"}>{job.status}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
      <Card title="New job">
        <NewJobForm />
      </Card>
    </div>
  );
}
