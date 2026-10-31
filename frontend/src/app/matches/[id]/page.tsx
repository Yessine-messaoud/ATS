import type { Metadata } from "next";
import Link from "next/link";
import { Info, TriangleAlert } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { Badge, Card, Notice, PageHeader, STATUS_TONE, ScoreBar, ScoreRing } from "@/components/ui";
import { api } from "@/lib/api";

export const metadata: Metadata = { title: "Match details" };

const DIMENSION_LABELS: Record<string, string> = {
  required_skills: "Required skills",
  preferred_skills: "Preferred skills",
  experience: "Experience",
  seniority: "Seniority",
  languages: "Languages",
  education: "Education",
  location: "Location / work mode",
};

export default async function MatchPage(props: PageProps<"/matches/[id]">) {
  const { id } = await props.params;
  const match = await api.match(id);
  const [candidate, job] = await Promise.all([api.candidate(match.candidate_id), api.job(match.job_id)]);
  const { result } = match;
  const explanation = result.explanation;

  return (
    <div className="space-y-4">
      <PageHeader
        crumbs={[
          { label: "Jobs", href: "/jobs" },
          { label: job.profile.title, href: `/jobs/${job.id}` },
          { label: "Match details" },
        ]}
        title={
          <span className="flex items-center gap-3">
            <Avatar id={candidate.id} name={candidate.profile.identity?.full_name} size="lg" />
            <span>
              <Link href={`/candidates/${candidate.id}`} className="hover:underline">
                {candidate.profile.identity?.full_name ?? "Candidate"}
              </Link>
              <span className="block text-sm font-normal text-zinc-500">for {job.profile.title}</span>
            </span>
          </span>
        }
      />

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <ScoreRing score={result.overall_score} size={72} />
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            {result.passed_knockouts ? (
              <Badge tone="green">mandatory criteria met</Badge>
            ) : (
              <Badge tone="red">a mandatory criterion is not met</Badge>
            )}
            {!result.requirements_validated && <Badge tone="amber">requirements not validated</Badge>}
          </div>
          <p className="text-sm text-zinc-500">
            {result.overall_score.toFixed(1)} / 100
            {result.penalty_multiplier < 1 &&
              ` · ${result.raw_score.toFixed(1)} before the penalty for ${result.missing_required.length} missing required skill(s)`}
          </p>
        </div>
      </div>

      {explanation && (
        <Card title="Explanation" actions={<Badge tone={explanation.source === "llm" ? "blue" : "neutral"}>{explanation.source === "llm" ? "AI-written, fact-checked" : "generated from the score factors"}</Badge>}>
          <p className="text-sm">{explanation.summary}</p>
          <div className="mt-3 grid gap-4 md:grid-cols-3">
            <ClaimList title="Strengths" claims={explanation.strengths ?? []} />
            <ClaimList title="Gaps" claims={explanation.gaps ?? []} />
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Interview questions</h3>
              <ul className="list-disc space-y-1 pl-4 text-sm">
                {(explanation.interview_questions ?? []).map((q) => (
                  <li key={q.question}>{q.question}</li>
                ))}
              </ul>
            </div>
          </div>
          {!!explanation.dropped_claims?.length && (
            <details className="mt-3 text-xs text-zinc-500">
              <summary>{explanation.dropped_claims.length} AI claim(s) removed because they were not supported by the factors</summary>
              <ul className="mt-1 list-disc pl-4">
                {explanation.dropped_claims.map((claim) => (
                  <li key={claim}>{claim}</li>
                ))}
              </ul>
            </details>
          )}
        </Card>
      )}

      {result.knockouts.length > 0 && (
        <Card title="Mandatory criteria">
          <ul className="space-y-1 text-sm">
            {result.knockouts.map((k) => (
              <li key={k.factor_id} className="flex items-center gap-2">
                <Badge tone={STATUS_TONE[k.status]}>{k.status}</Badge>
                {k.criterion}
                <span className="text-zinc-500">— {k.detail}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Score breakdown">
        <div className="space-y-4">
          {result.dimensions.map((dimension) => (
            <div key={dimension.name}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-medium">
                  {DIMENSION_LABELS[dimension.name] ?? dimension.name}
                  <span className="ml-2 text-xs font-normal text-zinc-500">
                    weight {Math.round(dimension.weight * 100)}% · {dimension.points.toFixed(1)} points
                  </span>
                </h3>
                <ScoreBar score={dimension.score} max={1} />
              </div>
              <ul className="mt-1 space-y-0.5 text-sm">
                {(dimension.factors ?? []).map((factor) => (
                  <li key={factor.id} className="flex items-baseline gap-2">
                    <Badge tone={STATUS_TONE[factor.status]}>{factor.status}</Badge>
                    <span className="font-medium">{factor.label}</span>
                    <span className="text-zinc-500">{factor.detail}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Card>
      {!!result.ignored_unverified?.length && (
        <Notice icon={<TriangleAlert />}>
          Claimed but not found in the CV, so not counted: {result.ignored_unverified.join(", ")}. Confirm them on the
          candidate page if they are correct.
        </Notice>
      )}
      <p className="flex items-start gap-1.5 text-xs text-zinc-500">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        Engine {result.engine_version}, computed {new Date(match.created_at).toLocaleString("en-GB")}. Deterministic: no
        AI is involved in the score.
      </p>
    </div>
  );
}

function ClaimList({ title, claims }: { title: string; claims: { text: string }[] }) {
  return (
    <div>
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</h3>
      <ul className="list-disc space-y-1 pl-4 text-sm">
        {claims.map((claim) => (
          <li key={claim.text}>{claim.text}</li>
        ))}
      </ul>
    </div>
  );
}
