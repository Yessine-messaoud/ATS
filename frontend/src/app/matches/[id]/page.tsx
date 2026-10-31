import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Bot, CheckCircle2, CircleAlert, Cpu, Gavel, History, Info, MessageCircleQuestion, TriangleAlert, XCircle } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { ContactList, DocumentPreview } from "@/components/candidate-parts";
import { DecisionPanel } from "@/components/decision-panel";
import { Badge, Card, Notice, PageHeader, ProgressBar, STATUS_TONE, ScoreRing, cx } from "@/components/ui";
import { ApiError, api, type CandidateDocument, type MatchResult } from "@/lib/api";
import { STAGE_LABELS } from "@/lib/enums";
import { formatDate, timeAgo } from "@/lib/format";

export const metadata: Metadata = { title: "CV evaluation" };

const DIMENSION_LABELS: Record<string, string> = {
  required_skills: "Required skills",
  preferred_skills: "Preferred skills",
  experience: "Experience relevance",
  seniority: "Seniority",
  languages: "Languages",
  education: "Education compatibility",
  location: "Location & work mode",
};

async function documentOrNull(id: string): Promise<CandidateDocument | null> {
  try {
    return await api.document(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

function coverage(result: MatchResult, name: string) {
  const dimension = result.dimensions.find((d) => d.name === name);
  const factors = dimension?.factors ?? [];
  return { dimension, met: factors.filter((f) => f.status === "met").length, total: factors.length, factors };
}

function SkillList({ factors }: { factors: MatchResult["dimensions"][number]["factors"] }) {
  if (!factors?.length) return <p className="text-xs text-zinc-500">None defined for this job.</p>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {factors.map((factor) => (
        <li key={factor.id}>
          <Badge tone={STATUS_TONE[factor.status] ?? "neutral"} title={factor.detail}>
            {factor.status === "met" ? <CheckCircle2 className="size-3" aria-hidden /> : factor.status === "missing" ? <XCircle className="size-3" aria-hidden /> : <CircleAlert className="size-3" aria-hidden />}
            {factor.label}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

function LayerLabel({ icon, children, tone }: { icon: ReactNode; children: ReactNode; tone: "engine" | "ai" | "human" }) {
  const styles = {
    engine: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    ai: "bg-lavender-100 text-lavender-600 dark:bg-violet-950 dark:text-violet-300",
    human: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  };
  return <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold [&>svg]:size-3", styles[tone])}>{icon}{children}</span>;
}

export default async function EvaluationPage(props: PageProps<"/matches/[id]">) {
  const { id } = await props.params;
  const match = await api.match(id);
  const [candidate, job, document, applications] = await Promise.all([
    api.candidate(match.candidate_id),
    api.job(match.job_id),
    documentOrNull(match.candidate_id),
    api.applications(match.job_id, false),
  ]);
  const application = applications.find((a) => a.candidate_id === candidate.id) ?? null;
  const history = application ? await api.audit({ entity_id: application.id, limit: "20" }) : [];
  const { result } = match;
  const explanation = result.explanation;
  const name = candidate.profile.identity?.full_name ?? "Candidate";
  const required = coverage(result, "required_skills");
  const preferred = coverage(result, "preferred_skills");
  const otherDimensions = result.dimensions.filter((d) => !["required_skills", "preferred_skills"].includes(d.name));

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[
          { label: "CV Evaluation", href: "/evaluations" },
          { label: job.profile.title, href: `/jobs/${job.id}` },
          { label: name },
        ]}
        title={
          <span className="flex items-center gap-3">
            <Avatar id={candidate.id} name={name} size="lg" />
            <span>
              <Link href={`/candidates/${candidate.id}`} className="hover:underline">
                {name}
              </Link>
              <span className="block text-sm font-normal text-zinc-500">
                {candidate.profile.professional_title ?? "Candidate"} · evaluated for {job.profile.title}
              </span>
            </span>
          </span>
        }
        badges={application ? <Badge tone="indigo">{STAGE_LABELS[application.stage]}</Badge> : <Badge>not in pipeline</Badge>}
      />

      <Notice tone="blue" icon={<Info />}>
        The score comes from a deterministic engine, the summary from an AI model: both support your judgement. Neither ever
        rejects or advances a candidate; only the recruiter decision below changes the pipeline.
      </Notice>

      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-6">
          <Card title="Matching analysis" actions={<LayerLabel icon={<Cpu />} tone="engine">Scoring engine · deterministic</LayerLabel>}>
            <div className="flex flex-col gap-6 md:flex-row">
              <div className="flex flex-col items-center gap-2 md:w-44">
                <ScoreRing score={result.overall_score} size={132} />
                <p className="text-xs text-zinc-500">Overall match / 100</p>
                {result.passed_knockouts ? <Badge tone="green">mandatory criteria met</Badge> : <Badge tone="red">a mandatory criterion is not met</Badge>}
                {result.penalty_multiplier < 1 && (
                  <p className="text-center text-[11px] text-zinc-500">
                    {result.raw_score.toFixed(1)} before the penalty for {result.missing_required.length} missing required skill(s)
                  </p>
                )}
                {!result.requirements_validated && <Badge tone="amber">requirements not validated</Badge>}
              </div>
              <div className="min-w-0 flex-1 space-y-5">
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="space-y-2">
                    <ProgressBar label="Required skills coverage" value={required.dimension?.score ?? 0} detail={`${required.met} of ${required.total} fully met`} />
                    <SkillList factors={required.factors} />
                  </div>
                  <div className="space-y-2">
                    <ProgressBar label="Preferred skills coverage" value={preferred.dimension?.score ?? 0} detail={`${preferred.met} of ${preferred.total} fully met`} />
                    <SkillList factors={preferred.factors} />
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  {otherDimensions.map((dimension) => (
                    <ProgressBar
                      key={dimension.name}
                      label={DIMENSION_LABELS[dimension.name] ?? dimension.name}
                      value={dimension.score}
                      detail={`weight ${Math.round(dimension.weight * 100)}% · ${(dimension.factors ?? []).map((f) => f.detail).filter(Boolean).slice(0, 1).join("") || `${dimension.points.toFixed(1)} points`}`}
                    />
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card title="Strengths" actions={<LayerLabel icon={<Cpu />} tone="engine">From the score factors</LayerLabel>}>
              <ul className="space-y-2 text-sm">
                {result.dimensions.flatMap((d) => (d.factors ?? []).filter((f) => f.status === "met")).slice(0, 8).map((factor) => (
                  <li key={factor.id} className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-500" aria-hidden />
                    <span>
                      <span className="font-medium">{factor.label}</span> <span className="text-zinc-500">{factor.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Missing requirements" actions={<LayerLabel icon={<Cpu />} tone="engine">From the score factors</LayerLabel>}>
              {result.knockouts.filter((k) => k.status !== "pass").length + result.dimensions.flatMap((d) => (d.factors ?? []).filter((f) => f.status !== "met")).length === 0 ? (
                <p className="text-sm text-zinc-500">Nothing missing.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {result.knockouts
                    .filter((k) => k.status !== "pass")
                    .map((k) => (
                      <li key={k.factor_id} className="flex items-start gap-2">
                        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-red-500" aria-hidden />
                        <span>
                          <span className="font-medium">Mandatory: {k.criterion}</span> <span className="text-zinc-500">({k.status}) {k.detail}</span>
                        </span>
                      </li>
                    ))}
                  {result.dimensions.flatMap((d) => (d.factors ?? []).filter((f) => f.status !== "met")).slice(0, 8).map((factor) => (
                    <li key={factor.id} className="flex items-start gap-2">
                      <XCircle className={cx("mt-0.5 size-4 shrink-0", factor.status === "missing" ? "text-red-500" : "text-amber-500")} aria-hidden />
                      <span>
                        <span className="font-medium">{factor.label}</span> <span className="text-zinc-500">{factor.detail}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {!!result.ignored_unverified?.length && (
                <p className="mt-3 rounded-md bg-amber-50 px-2 py-1.5 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  Claimed but not found in the CV, so not counted: {result.ignored_unverified.join(", ")}.{" "}
                  <Link href={`/candidates/${candidate.id}?tab=profile`} className="font-medium underline">
                    Confirm on the profile
                  </Link>
                </p>
              )}
            </Card>
          </div>

          <section className="rounded-xl border border-violet-200 bg-gradient-to-b from-lavender-50 to-white p-5 shadow-sm dark:border-violet-900/60 dark:from-violet-950/30 dark:to-zinc-900">
            <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Evaluation summary</h2>
              <LayerLabel icon={<Bot />} tone="ai">
                {explanation?.source === "llm" ? "AI-generated · fact-checked against the factors" : "Generated from the score factors (no AI)"}
              </LayerLabel>
            </header>
            {explanation ? (
              <div className="space-y-4">
                <p className="text-sm leading-relaxed">{explanation.summary}</p>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Strengths noted</h3>
                    <ul className="list-disc space-y-1 pl-4 text-sm">
                      {(explanation.strengths ?? []).map((claim) => (
                        <li key={claim.text}>{claim.text}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">Gaps noted</h3>
                    <ul className="list-disc space-y-1 pl-4 text-sm">
                      {(explanation.gaps ?? []).map((claim) => (
                        <li key={claim.text}>{claim.text}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                {!!explanation.interview_questions?.length && (
                  <div>
                    <h3 className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      <MessageCircleQuestion className="size-3.5" aria-hidden /> Suggested interview questions
                    </h3>
                    <ol className="list-decimal space-y-1 pl-5 text-sm">
                      {explanation.interview_questions.map((q) => (
                        <li key={q.question}>{q.question}</li>
                      ))}
                    </ol>
                  </div>
                )}
                {!!explanation.dropped_claims?.length && (
                  <details className="text-xs text-zinc-500">
                    <summary className="cursor-pointer">{explanation.dropped_claims.length} AI claim(s) removed because the factors did not support them</summary>
                    <ul className="mt-1 list-disc pl-4">
                      {explanation.dropped_claims.map((claim) => (
                        <li key={claim}>{claim}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">No summary for this evaluation.</p>
            )}
          </section>

          <Card title="CV">
            <DocumentPreview candidateId={candidate.id} document={document} height="40rem" />
          </Card>
        </div>

        <div className="space-y-6">
          <section className="rounded-xl border-2 border-emerald-200 bg-white p-5 shadow-sm dark:border-emerald-900/60 dark:bg-zinc-900">
            <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Recruiter decision</h2>
              <LayerLabel icon={<Gavel />} tone="human">Human decision</LayerLabel>
            </header>
            <DecisionPanel jobId={job.id} candidateId={candidate.id} application={application ? { id: application.id, stage: application.stage } : null} />
          </section>

          <Card title="Decision history" actions={<History className="size-4 text-zinc-400" aria-hidden />}>
            {history.length === 0 ? (
              <p className="text-sm text-zinc-500">No decision recorded yet.</p>
            ) : (
              <ol className="space-y-3 border-l border-zinc-200 pl-4 dark:border-zinc-800">
                {history.map((entry) => (
                  <li key={entry.id} className="relative text-sm">
                    <span className="absolute -left-[21px] top-1.5 size-2.5 rounded-full border-2 border-white bg-brand-500 dark:border-zinc-900" aria-hidden />
                    <p className="font-medium">
                      {entry.action === "application.stage_changed"
                        ? `${STAGE_LABELS[entry.details.from as keyof typeof STAGE_LABELS] ?? entry.details.from} → ${STAGE_LABELS[entry.details.to as keyof typeof STAGE_LABELS] ?? entry.details.to}`
                        : entry.action === "application.created"
                          ? "Added to the pipeline"
                          : entry.action}
                    </p>
                    {typeof entry.details.reason === "string" && entry.details.reason && (
                      <p className="mt-0.5 rounded-md bg-zinc-50 px-2 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">“{entry.details.reason}”</p>
                    )}
                    <p className="text-xs text-zinc-500">
                      {entry.actor} · {timeAgo(entry.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          <Card title="Candidate">
            <ContactList candidate={candidate} />
            <div className="mt-4 flex flex-wrap gap-1">
              {(candidate.profile.skills ?? []).slice(0, 12).map((skill) => (
                <Badge key={skill.name} tone={skill.verified === false ? "amber" : "neutral"} title={skill.verified === false ? "not found in the CV" : undefined}>
                  {skill.name}
                </Badge>
              ))}
            </div>
            <Link href={`/candidates/${candidate.id}`} className="mt-4 inline-block text-xs font-medium text-brand-600 hover:underline dark:text-brand-400">
              Full profile →
            </Link>
          </Card>

          <p className="text-xs text-zinc-500">
            Engine {result.engine_version} · evaluated {formatDate(match.created_at)}. Each evaluation is kept in the match history.
          </p>
        </div>
      </div>
    </div>
  );
}
