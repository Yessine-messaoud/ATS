import type { Metadata } from "next";
import Link from "next/link";
import { BadgeCheck, Briefcase, Cpu, FileText, ListChecks, ShieldAlert, ShieldCheck, TriangleAlert } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { ContactList, DocumentPreview, ExtractedText } from "@/components/candidate-parts";
import { EvaluateButton } from "@/components/evaluate-button";
import { JobIcon } from "@/components/job-visuals";
import { Badge, Card, Empty, Notice, PageHeader, ScoreRing, cx, focusRing } from "@/components/ui";
import { ApiError, api, type CandidateDocument } from "@/lib/api";
import { FLAG_LABELS, STAGE_LABELS } from "@/lib/enums";
import { formatDate } from "@/lib/format";
import { candidateFacts, evaluationStatus, yearsOfExperience } from "@/lib/insights";

import { Duplicates } from "./duplicates";
import { PrivacyPanel } from "./privacy-panel";
import { ProfileReview } from "./profile-review";

export async function generateMetadata(props: PageProps<"/candidates/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const candidate = await api.candidate(id);
  return { title: candidate.profile.identity?.full_name ?? "Candidate" };
}

async function documentOrNull(id: string): Promise<CandidateDocument | null> {
  try {
    return await api.document(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

const TABS = [
  { key: "evaluation", label: "Evaluation", icon: Cpu },
  { key: "profile", label: "Profile review", icon: ListChecks },
  { key: "document", label: "CV", icon: FileText },
  { key: "privacy", label: "Privacy", icon: ShieldCheck },
] as const;
type Tab = (typeof TABS)[number]["key"];

export default async function CandidatePage(props: PageProps<"/candidates/[id]">) {
  const { id } = await props.params;
  const { tab: tabParam } = await props.searchParams;
  const tab: Tab = TABS.some((t) => t.key === tabParam) ? (tabParam as Tab) : "evaluation";
  const [candidate, document, recommendations, duplicates, jobs] = await Promise.all([
    api.candidate(id),
    documentOrNull(id),
    api.recommendations(id),
    api.duplicates(id),
    api.jobs(),
  ]);
  const applications = (await Promise.all(jobs.map((job) => api.applications(job.id, false)))).flat().filter((a) => a.candidate_id === id);
  const name = candidate.profile.identity?.full_name ?? "Unnamed candidate";
  const facts = candidateFacts(candidate);
  const status = evaluationStatus(candidate);
  const years = yearsOfExperience(candidate);
  const best = recommendations[0];
  const extraction = candidate.extraction as { model?: string; prompt_version?: string; issues?: { path: string; message: string }[] };
  const jobTitle = new Map(jobs.map((j) => [j.id, j.profile.title]));

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: "Candidates", href: "/candidates" }, { label: name }]}
        title={
          <span className="flex items-center gap-3">
            <Avatar id={candidate.id} name={name} size="lg" />
            <span>
              {name}
              <span className="block text-sm font-normal text-zinc-500">
                {candidate.profile.professional_title ?? "No title"}
                {years !== null && ` · ${years} years of experience`}
              </span>
            </span>
          </span>
        }
        badges={
          <>
            {status === "verified" && (
              <Badge tone="green">
                <BadgeCheck className="size-3" aria-hidden /> profile verified
              </Badge>
            )}
            {status === "to_review" && (
              <Badge tone="amber">
                <TriangleAlert className="size-3" aria-hidden /> {facts.unverified} item(s) to verify
              </Badge>
            )}
            {status === "flagged" && (
              <Badge tone="red">
                <ShieldAlert className="size-3" aria-hidden /> document flagged
              </Badge>
            )}
            {candidate.talent_pool_consent && <Badge tone="indigo">talent pool</Badge>}
          </>
        }
      />

      <Duplicates candidateId={candidate.id} duplicates={duplicates} />

      <nav aria-label="Candidate sections" className="-mx-4 overflow-x-auto border-b border-zinc-200 px-4 dark:border-zinc-800 sm:mx-0 sm:px-0">
        <div className="flex gap-1">
          {TABS.map(({ key, label, icon: Icon }) => (
            <Link
              key={key}
              href={`/candidates/${id}${key === "evaluation" ? "" : `?tab=${key}`}`}
              aria-current={tab === key ? "page" : undefined}
              scroll={false}
              className={cx(
                "-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm",
                tab === key
                  ? "border-brand-600 font-medium text-brand-700 dark:border-brand-400 dark:text-brand-300"
                  : "border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100",
                focusRing,
              )}
            >
              <Icon className="size-4" aria-hidden />
              {label}
              {key === "profile" && facts.unverified > 0 && <span className="size-1.5 rounded-full bg-amber-500" aria-label="items to verify" />}
              {key === "document" && facts.security && <span className="size-1.5 rounded-full bg-red-500" aria-label="security flag" />}
            </Link>
          ))}
        </div>
      </nav>

      {tab === "evaluation" && (
        <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
          <div className="space-y-6">
            <Card title="Match with open jobs" description="Deterministic scores, best first. Open an evaluation for the full analysis and an AI-written summary." flush>
              {recommendations.length === 0 ? (
                <Empty icon={<Briefcase />}>No open job to compare with.</Empty>
              ) : (
                <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {recommendations.map((r) => (
                    <li key={r.job_id} className="flex flex-wrap items-center gap-4 px-4 py-3">
                      <JobIcon title={r.title} size="sm" />
                      <div className="min-w-0 flex-1">
                        <Link href={`/jobs/${r.job_id}`} className="font-medium hover:underline">
                          {r.title}
                        </Link>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {!r.passed_knockouts && <Badge tone="red">mandatory criterion not met</Badge>}
                          {r.missing_required.slice(0, 4).map((skill) => (
                            <Badge key={skill} tone="red" title="missing required skill">
                              ✗ {skill}
                            </Badge>
                          ))}
                          {r.passed_knockouts && r.missing_required.length === 0 && <Badge tone="green">all required skills</Badge>}
                        </div>
                      </div>
                      <ScoreRing score={r.overall_score} size={48} />
                      <EvaluateButton candidateId={candidate.id} jobId={r.job_id} />
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Applications" flush>
              {applications.length === 0 ? (
                <Empty>Not in any pipeline yet. Add them from a job&apos;s ranking or an evaluation.</Empty>
              ) : (
                <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {applications.map((a) => (
                    <li key={a.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                      <Link href={`/jobs/${a.job_id}/pipeline`} className="font-medium hover:underline">
                        {jobTitle.get(a.job_id)}
                      </Link>
                      <span className="flex items-center gap-3 text-xs text-zinc-500">
                        {formatDate(a.created_at)}
                        <Badge tone="indigo">{STAGE_LABELS[a.stage]}</Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
          <div className="space-y-6">
            <Card title="Contact">
              <ContactList candidate={candidate} />
            </Card>
            {best && (
              <Card title="Best match">
                <div className="flex items-center gap-4">
                  <ScoreRing score={best.overall_score} size={72} />
                  <div className="min-w-0 text-sm">
                    <p className="font-medium">{best.title}</p>
                    <p className="text-xs text-zinc-500">{best.passed_knockouts ? "All mandatory criteria met" : "A mandatory criterion is not met"}</p>
                  </div>
                </div>
              </Card>
            )}
            <Card title="Skills">
              <div className="flex flex-wrap gap-1">
                {(candidate.profile.skills ?? []).map((skill) => (
                  <Badge key={skill.name} tone={skill.verified === false ? "amber" : "neutral"} title={skill.verified === false ? "not found in the CV: no credit until confirmed" : undefined}>
                    {skill.name}
                  </Badge>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}

      {tab === "profile" && (
        <div className="space-y-4">
          {!!extraction.issues?.length && (
            <Notice icon={<TriangleAlert />}>Some extracted fields were invalid and dropped: {extraction.issues.map((i) => i.path).join(", ")}.</Notice>
          )}
          <p className="text-xs text-zinc-500">
            Extracted by {extraction.model ?? "?"} ({extraction.prompt_version ?? "?"}). Each item shows the quote it was taken from.
          </p>
          <div className="grid gap-6 xl:grid-cols-[1fr_26rem]">
            <ProfileReview candidateId={candidate.id} initial={candidate.profile} />
            <div className="xl:sticky xl:top-20 xl:self-start">
              <Card title="Source text">
                <ExtractedText text={document?.raw_text} height="36rem" />
              </Card>
            </div>
          </div>
        </div>
      )}

      {tab === "document" && (
        <div className="space-y-4">
          {document?.flags.includes("possible_prompt_injection") && (
            <Notice tone="red" icon={<ShieldAlert />}>
              <strong>Possible prompt injection.</strong> This document contains text addressed to an automated screening system. It
              was ignored for extraction, and scores are computed without the AI. Review the document manually.
            </Notice>
          )}
          {document?.flags.includes("hidden_text") && (
            <Notice tone="red" icon={<ShieldAlert />}>
              <strong>Hidden text found</strong> (white, tiny or off-page). It was excluded from extraction:
              <ul className="mt-1 list-disc pl-5 text-xs">
                {document.hidden_text.map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
            </Notice>
          )}
          {!!document?.flags.length && (
            <div className="flex flex-wrap gap-1">
              {document.flags.map((flag) => (
                <Badge key={flag} tone="amber">
                  {FLAG_LABELS[flag] ?? flag}
                </Badge>
              ))}
            </div>
          )}
          <Card>
            <DocumentPreview candidateId={candidate.id} document={document} />
          </Card>
        </div>
      )}

      {tab === "privacy" && (
        <div className="max-w-2xl">
          <PrivacyPanel
            candidateId={candidate.id}
            consent={candidate.talent_pool_consent}
            consentUpdatedAt={candidate.consent_updated_at}
            purgeAfter={document?.purged_at ? null : (document?.purge_after ?? null)}
          />
        </div>
      )}
    </div>
  );
}
