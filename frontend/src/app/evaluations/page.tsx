import type { Metadata } from "next";
import Link from "next/link";
import { FileCheck2, History, ShieldAlert, TriangleAlert } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { EvaluateButton } from "@/components/evaluate-button";
import { JobIcon } from "@/components/job-visuals";
import { Badge, Card, Empty, PageHeader, ScoreBar, cx, focusRing } from "@/components/ui";
import { api, loadWorkspace } from "@/lib/api";
import { STAGE_LABELS } from "@/lib/enums";
import { formatDate, timeAgo } from "@/lib/format";
import { candidateFacts } from "@/lib/insights";

export const metadata: Metadata = { title: "CV Evaluation" };

const QUEUE_STAGES = new Set(["new", "screening"]);

export default async function EvaluationsPage() {
  const [{ jobs, candidates, applications }, scored] = await Promise.all([
    loadWorkspace(),
    api.audit({ action: "match.scored", limit: "12" }),
  ]);
  const jobsById = new Map(jobs.map((job) => [job.id, job]));
  const candidatesById = new Map(candidates.map((c) => [c.id, c]));
  const queue = applications
    .filter((a) => QUEUE_STAGES.has(a.stage) && jobsById.get(a.job_id)?.status === "open")
    .sort((a, b) => (b.overall_score ?? 0) - (a.overall_score ?? 0));
  const toVerify = candidates.filter((c) => {
    const facts = candidateFacts(c);
    return facts.security || facts.unverified > 0;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="CV Evaluation"
        description="Applications waiting for a recruiter's assessment. Each evaluation combines the deterministic score with an AI-written summary; you decide."
      />

      <Card flush title="Evaluation queue" description={`${queue.length} application${queue.length === 1 ? "" : "s"} in the New or Screening stage of an open job, best score first`}>
        {queue.length === 0 ? (
          <Empty icon={<FileCheck2 />} title="Nothing waiting">
            Add candidates to a job&apos;s pipeline from its ranking to evaluate them here.
          </Empty>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[48rem] text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50/80 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Candidate</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Job</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Stage</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Match score</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Since</th>
                  <th scope="col" className="px-4 py-2.5"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {queue.map((application) => {
                  const job = jobsById.get(application.job_id);
                  return (
                    <tr key={application.id} className="hover:bg-brand-50/40 dark:hover:bg-zinc-800/40">
                      <td className="px-4 py-3">
                        <Link href={`/candidates/${application.candidate_id}`} className={cx("flex items-center gap-3 rounded-md font-medium hover:underline", focusRing)}>
                          <Avatar id={application.candidate_id} name={application.display_name} size="sm" />
                          {application.display_name}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2">
                          <JobIcon title={job?.profile.title ?? ""} size="sm" />
                          {job?.profile.title}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={application.stage === "new" ? "neutral" : "blue"}>{STAGE_LABELS[application.stage]}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {application.overall_score !== null && application.overall_score !== undefined ? <ScoreBar score={application.overall_score} /> : "—"}
                          {application.passed_knockouts === false && <Badge tone="red">criterion not met</Badge>}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-500">{timeAgo(application.updated_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <EvaluateButton candidateId={application.candidate_id} jobId={application.job_id} variant="primary" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card flush title="Recent evaluations" actions={<History className="size-4 text-zinc-400" aria-hidden />}>
          {scored.length === 0 ? (
            <Empty>No evaluation yet.</Empty>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {scored.map((entry) => {
                const candidate = candidatesById.get(String(entry.details.candidate_id));
                const job = jobsById.get(String(entry.details.job_id));
                const score = typeof entry.details.score === "number" ? entry.details.score : null;
                return (
                  <li key={entry.id}>
                    <Link href={`/matches/${entry.entity_id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                      <Avatar id={String(entry.details.candidate_id)} name={candidate?.profile.identity?.full_name ?? "?"} size="sm" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{candidate?.profile.identity?.full_name ?? "Erased candidate"}</span>
                        <span className="block truncate text-xs text-zinc-500">{job?.profile.title ?? "Job"} · {formatDate(entry.created_at)}</span>
                      </span>
                      {score !== null && <span className="text-sm font-semibold tabular-nums">{score.toFixed(1)}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card flush title="Profiles to verify" description="Extracted items not found in the CV, or documents with hidden text.">
          {toVerify.length === 0 ? (
            <Empty>All profiles are verified.</Empty>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {toVerify.map((candidate) => {
                const facts = candidateFacts(candidate);
                const name = candidate.profile.identity?.full_name ?? "Unnamed candidate";
                return (
                  <li key={candidate.id}>
                    <Link href={`/candidates/${candidate.id}?tab=${facts.security ? "document" : "profile"}`} className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                      <Avatar id={candidate.id} name={name} size="sm" />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium">{name}</span>
                      {facts.security && (
                        <Badge tone="red">
                          <ShieldAlert className="size-3" aria-hidden /> flagged
                        </Badge>
                      )}
                      {facts.unverified > 0 && (
                        <Badge tone="amber">
                          <TriangleAlert className="size-3" aria-hidden /> {facts.unverified} to verify
                        </Badge>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
