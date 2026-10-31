// Derived views over the API data (no new backend logic): to-do items, KPIs and candidate summaries.
import type { Application, Candidate, Job, Ranking } from "./api";

export const SECURITY_FLAGS = new Set(["hidden_text", "possible_prompt_injection"]);
export const SHORTLIST_STAGES = new Set(["interview", "offer", "hired"]);
export const CLOSED_STAGES = new Set(["hired", "rejected", "withdrawn"]);

export type Task = {
  key: string;
  kind: "validate" | "security" | "verify" | "screen";
  title: string;
  detail: string;
  href: string;
};

export function candidateFacts(candidate: Candidate) {
  const flags = (candidate.extraction.document_flags as string[] | undefined) ?? [];
  const unverified = (candidate.extraction.evidence as { unverified?: number } | undefined)?.unverified ?? 0;
  return { security: flags.some((f) => SECURITY_FLAGS.has(f)), unverified, flags };
}

/** What a recruiter should look at next, from real data only. */
export function tasks(jobs: Job[], candidates: Candidate[], applications: Application[]): Task[] {
  const list: Task[] = [];
  for (const job of jobs.filter((j) => j.status === "open" && !j.requirements_validated)) {
    list.push({
      key: `validate-${job.id}`,
      kind: "validate",
      title: `Validate the requirements of ${job.profile.title}`,
      detail: "Rankings use unvalidated requirements until you review them.",
      href: `/jobs/${job.id}/requirements`,
    });
  }
  for (const candidate of candidates) {
    const { security, unverified } = candidateFacts(candidate);
    const name = candidate.profile.identity?.full_name ?? "Unnamed candidate";
    if (security) {
      list.push({
        key: `flag-${candidate.id}`,
        kind: "security",
        title: `Check ${name}'s document`,
        detail: "Hidden text or text addressed to an AI was found in the file.",
        href: `/candidates/${candidate.id}?tab=document`,
      });
    }
    if (unverified > 0) {
      list.push({
        key: `verify-${candidate.id}`,
        kind: "verify",
        title: `Review ${unverified} unverified item${unverified > 1 ? "s" : ""} for ${name}`,
        detail: "They earn no credit in matching until you confirm them.",
        href: `/candidates/${candidate.id}?tab=profile`,
      });
    }
  }
  for (const job of jobs) {
    const waiting = applications.filter((a) => a.job_id === job.id && a.stage === "new").length;
    if (waiting > 0) {
      list.push({
        key: `screen-${job.id}`,
        kind: "screen",
        title: `Screen ${waiting} new application${waiting > 1 ? "s" : ""} for ${job.profile.title}`,
        detail: "They are waiting in the first stage of the pipeline.",
        href: `/jobs/${job.id}/pipeline`,
      });
    }
  }
  return list;
}

export function kpis(jobs: Job[], applications: Application[]) {
  return {
    activeJobs: jobs.filter((j) => j.status === "open").length,
    closedJobs: jobs.filter((j) => j.status !== "open").length,
    applications: applications.length,
    activeApplications: applications.filter((a) => !CLOSED_STAGES.has(a.stage)).length,
    shortlisted: applications.filter((a) => SHORTLIST_STAGES.has(a.stage)).length,
    // Applications not looked at yet: still in the first pipeline stage.
    pendingEvaluations: applications.filter((a) => a.stage === "new").length,
  };
}

/** Best deterministic score per candidate across the given rankings (passed and knocked out). */
export function bestScores(rankings: Ranking[]): Map<string, { score: number; jobId: string; passed: boolean }> {
  const best = new Map<string, { score: number; jobId: string; passed: boolean }>();
  for (const ranking of rankings) {
    for (const row of [...ranking.ranked, ...ranking.knocked_out]) {
      const current = best.get(row.candidate_id);
      if (!current || row.overall_score > current.score) {
        best.set(row.candidate_id, { score: row.overall_score, jobId: ranking.job_id, passed: row.passed_knockouts });
      }
    }
  }
  return best;
}

/** Years of experience: as stated, else from the positions' dates with overlapping periods counted once. */
export function yearsOfExperience(candidate: Candidate, today = new Date()): number | null {
  if (typeof candidate.profile.total_years_experience === "number") return candidate.profile.total_years_experience;
  const periods = (candidate.profile.experiences ?? [])
    .map((e) => {
      const start = e.dates?.start_date ? +new Date(e.dates.start_date) : null;
      const end = e.dates?.end_date ? +new Date(e.dates.end_date) : e.current ? +today : null;
      return start !== null && end !== null && end > start ? [start, end] : null;
    })
    .filter((p): p is number[] => p !== null)
    .sort((a, b) => a[0] - b[0]);
  let total = 0;
  let cursor = 0;
  for (const [start, end] of periods) {
    const from = Math.max(start, cursor);
    if (end > from) total += end - from;
    cursor = Math.max(cursor, end);
  }
  if (total === 0) {
    const months = (candidate.profile.experiences ?? []).reduce((sum, e) => sum + (e.duration_months ?? 0), 0);
    return months ? Math.round((months / 12) * 10) / 10 : null;
  }
  return Math.round((total / (365.25 * 86_400_000)) * 10) / 10;
}

export type EvaluationStatus = "flagged" | "to_review" | "verified";

export function evaluationStatus(candidate: Candidate): EvaluationStatus {
  const { security, unverified } = candidateFacts(candidate);
  if (security) return "flagged";
  return unverified > 0 ? "to_review" : "verified";
}
