import type { Metadata } from "next";
import { CheckCircle2, ShieldAlert, TriangleAlert, Users } from "lucide-react";

import { Card, Notice, PageHeader, Stat } from "@/components/ui";
import { loadWorkspace } from "@/lib/api";
import { bestScores, candidateFacts, evaluationStatus, yearsOfExperience } from "@/lib/insights";

import { CandidatesTable, type CandidateRow } from "./candidates-table";

export const metadata: Metadata = { title: "Candidates" };

export default async function CandidatesPage(props: PageProps<"/candidates">) {
  const [{ jobs, candidates, applications, rankings }, params] = await Promise.all([loadWorkspace({ rankings: true }), props.searchParams]);
  const titles = new Map(jobs.map((job) => [job.id, job.profile.title]));
  const best = bestScores(rankings);

  const rows: CandidateRow[] = candidates.map((candidate) => {
    const mine = applications.filter((a) => a.candidate_id === candidate.id);
    const score = best.get(candidate.id);
    const latest = mine.map((a) => a.created_at).sort().at(-1);
    return {
      id: candidate.id,
      name: candidate.profile.identity?.full_name ?? "Unnamed candidate",
      title: candidate.profile.professional_title ?? null,
      applied: mine.map((a) => ({ jobId: a.job_id, title: titles.get(a.job_id) ?? "Job", stage: a.stage })),
      years: yearsOfExperience(candidate),
      skills: (candidate.profile.skills ?? []).map((s) => s.name),
      date: latest ?? candidate.created_at,
      status: evaluationStatus(candidate),
      unverified: candidateFacts(candidate).unverified,
      score: score ? { value: score.score, job: titles.get(score.jobId) ?? "", passed: score.passed } : null,
      consent: candidate.talent_pool_consent,
    };
  });
  const count = (status: CandidateRow["status"]) => rows.filter((r) => r.status === status).length;

  return (
    <div className="space-y-6">
      <PageHeader title="Candidates" description="The talent pool. Every extracted item is checked against the source document." />
      {params.erased && (
        <Notice tone="green" icon={<CheckCircle2 />}>
          The candidate and all their personal data were erased. The erasure is recorded in the audit log.
        </Notice>
      )}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Candidates" value={rows.length} hint={`${rows.filter((r) => r.applied.length).length} with an application`} icon={<Users />} />
        <Stat label="Verified profiles" value={count("verified")} hint="every item found in the CV" icon={<CheckCircle2 />} />
        <Stat label="To review" value={count("to_review")} hint="unverified items to confirm" icon={<TriangleAlert />} />
        <Stat label="Flagged documents" value={count("flagged")} hint="hidden text or injection" icon={<ShieldAlert />} />
      </div>
      <Card flush>
        <CandidatesTable rows={rows} jobs={jobs.map((j) => ({ id: j.id, title: j.profile.title }))} startWithUpload={params.upload === "1"} />
      </Card>
    </div>
  );
}
