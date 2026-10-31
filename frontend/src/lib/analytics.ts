// Analytics series, computed from the API data. Every number here is real; sample data lives in sample-data.ts.
import type { Application, AuditEntry, Candidate, Job, Ranking } from "./api";
import { STAGE_LABELS } from "./enums";
import { bestScores } from "./insights";

export type RangeKey = "7" | "30" | "90" | "custom";
export type DateRange = { key: RangeKey; from: Date; to: Date };

const DAY = 86_400_000;
const FUNNEL = ["new", "screening", "interview", "offer", "hired"] as const;

export function parseRange(params: Record<string, string | string[] | undefined>, now = new Date()): DateRange {
  const value = (name: string) => (typeof params[name] === "string" ? (params[name] as string) : undefined);
  const key = (["7", "30", "90", "custom"].includes(value("range") ?? "") ? value("range") : "30") as RangeKey;
  if (key === "custom") {
    const from = value("from") ? new Date(`${value("from")}T00:00:00`) : null;
    const to = value("to") ? new Date(`${value("to")}T23:59:59`) : null;
    if (from && to && !isNaN(+from) && !isNaN(+to) && from <= to) return { key, from, to };
  }
  const days = key === "custom" ? 30 : Number(key);
  return { key: key === "custom" ? "30" : key, from: new Date(+now - days * DAY), to: now };
}

const inRange = (iso: string, range: DateRange) => {
  const time = +new Date(iso);
  return time >= +range.from && time <= +range.to;
};

const dayLabel = (date: Date) => date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** Applications per day (ranges up to 31 days) or per week. */
export function applicationsOverTime(applications: Application[], range: DateRange) {
  const days = Math.max(1, Math.ceil((+range.to - +range.from) / DAY));
  const step = days > 31 ? 7 : 1;
  const buckets: { label: string; start: number; value: number }[] = [];
  for (let start = +range.from; start < +range.to; start += step * DAY) {
    buckets.push({ label: dayLabel(new Date(start)), start, value: 0 });
  }
  for (const application of applications) {
    const time = +new Date(application.created_at);
    if (time < +range.from || time > +range.to) continue;
    const index = Math.min(buckets.length - 1, Math.floor((time - +range.from) / (step * DAY)));
    if (index >= 0) buckets[index].value += 1;
  }
  return { series: buckets.map(({ label, value }) => ({ label, value })), granularity: step === 1 ? "day" : "week" };
}

export function pipelineBreakdown(applications: Application[]) {
  return (Object.keys(STAGE_LABELS) as (keyof typeof STAGE_LABELS)[]).map((stage) => ({
    key: stage,
    label: STAGE_LABELS[stage],
    value: applications.filter((a) => a.stage === stage).length,
  }));
}

/** Furthest active stage each application reached (from the audit trail of stage changes, plus its current stage). */
export function funnel(applications: Application[], stageChanges: AuditEntry[]) {
  const reached = new Map<string, number>();
  const rank = (stage: unknown) => FUNNEL.indexOf(stage as (typeof FUNNEL)[number]);
  for (const application of applications) reached.set(application.id, Math.max(0, rank(application.stage)));
  for (const entry of stageChanges) {
    const id = entry.entity_id;
    if (!id || !reached.has(id)) continue;
    const furthest = Math.max(rank(entry.details.from), rank(entry.details.to));
    reached.set(id, Math.max(reached.get(id) ?? 0, furthest));
  }
  return FUNNEL.map((stage, index) => ({
    label: index === 0 ? "Applied" : STAGE_LABELS[stage],
    value: [...reached.values()].filter((value) => value >= index).length,
  }));
}

/** Share of candidates (in %) listing each skill, top `limit`. */
export function topSkills(candidates: Candidate[], limit = 8) {
  if (candidates.length === 0) return [];
  const counts = new Map<string, number>();
  for (const candidate of candidates) {
    const names = new Set((candidate.profile.skills ?? []).map((s) => s.name.trim()).filter(Boolean));
    for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([label, count]) => ({ label, value: Math.round((count / candidates.length) * 100) }));
}

export function applicationsPerJob(jobs: Job[], applications: Application[]) {
  return jobs
    .map((job) => {
      const mine = applications.filter((a) => a.job_id === job.id);
      return {
        label: job.profile.title.length > 22 ? `${job.profile.title.slice(0, 21)}…` : job.profile.title,
        applications: mine.length,
        shortlisted: mine.filter((a) => ["interview", "offer", "hired"].includes(a.stage)).length,
      };
    })
    .filter((row) => row.applications > 0)
    .sort((a, b) => b.applications - a.applications);
}

/** Each candidate's best score across the open jobs, in buckets of 10 points. */
export function scoreDistribution(rankings: Ranking[], candidateIds: Set<string>) {
  const buckets = Array.from({ length: 10 }, (_, i) => ({ label: `${i * 10}–${i * 10 + 9}`, value: 0 }));
  buckets[9].label = "90–100";
  for (const [candidateId, best] of bestScores(rankings)) {
    if (!candidateIds.has(candidateId)) continue;
    buckets[Math.min(9, Math.floor(best.score / 10))].value += 1;
  }
  return buckets;
}

export function analytics(
  data: { jobs: Job[]; candidates: Candidate[]; applications: Application[]; rankings: Ranking[] },
  stageChanges: AuditEntry[],
  range: DateRange,
) {
  const applications = data.applications.filter((a) => inRange(a.created_at, range));
  const candidates = data.candidates.filter((c) => inRange(c.created_at, range));
  return {
    overTime: applicationsOverTime(data.applications, range),
    pipeline: pipelineBreakdown(applications),
    funnel: funnel(applications, stageChanges),
    skills: topSkills(candidates),
    perJob: applicationsPerJob(data.jobs, applications),
    scores: scoreDistribution(data.rankings, new Set(candidates.map((c) => c.id))),
    totals: { applications: applications.length, candidates: candidates.length },
  };
}

export type Analytics = ReturnType<typeof analytics>;
