import type { Metadata } from "next";
import Link from "next/link";

import { ExternalLink, FileText, ShieldAlert, TriangleAlert } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { Badge, Card, Empty, Notice, PageHeader } from "@/components/ui";
import { ApiError, api, type CandidateDocument } from "@/lib/api";
import { FLAG_LABELS } from "@/lib/enums";

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

export default async function CandidatePage(props: PageProps<"/candidates/[id]">) {
  const { id } = await props.params;
  const [candidate, document, recommendations, duplicates] = await Promise.all([
    api.candidate(id),
    documentOrNull(id),
    api.recommendations(id),
    api.duplicates(id),
  ]);
  const name = candidate.profile.identity?.full_name ?? "Unnamed candidate";
  const extraction = candidate.extraction as {
    model?: string;
    prompt_version?: string;
    issues?: { path: string; message: string }[];
  };

  return (
    <div className="space-y-4">
      <PageHeader
        crumbs={[{ label: "Candidates", href: "/candidates" }, { label: name }]}
        title={
          <span className="flex items-center gap-3">
            <Avatar id={candidate.id} name={name} size="lg" />
            {name}
          </span>
        }
        badges={candidate.talent_pool_consent ? <Badge tone="indigo">talent pool</Badge> : undefined}
        description={`${candidate.profile.professional_title ?? "No title"} · extracted by ${extraction.model ?? "?"} (${extraction.prompt_version ?? "?"})`}
      />

      <Duplicates candidateId={candidate.id} duplicates={duplicates} />
      {document?.flags.includes("possible_prompt_injection") && (
        <Notice tone="red" icon={<ShieldAlert />}>
          <strong>Possible prompt injection.</strong> This document contains text addressed to an automated screening
          system. It was ignored for extraction, and scores are computed without the LLM. Review the document manually.
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
      {!!extraction.issues?.length && (
        <Notice icon={<TriangleAlert />}>
          Some extracted fields were invalid and dropped: {extraction.issues.map((i) => i.path).join(", ")}.
        </Notice>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <ProfileReview candidateId={candidate.id} initial={candidate.profile} />
        <div className="space-y-4">
          <Card
            title="Source document"
            actions={
              document &&
              !document.purged_at && (
                <a
                  href={`/candidates/${id}/file`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                >
                  Open original <ExternalLink className="size-3" aria-hidden />
                </a>
              )
            }
          >
            {document?.purged_at ? (
              <Empty>
                Deleted on {new Date(document.purged_at).toLocaleDateString("en-GB")} under the retention policy. The
                extracted profile is kept.
              </Empty>
            ) : document ? (
              <>
                <div className="mb-2 flex flex-wrap gap-1">
                  {document.flags.map((flag) => (
                    <Badge key={flag} tone="amber">
                      {FLAG_LABELS[flag] ?? flag}
                    </Badge>
                  ))}
                </div>
                <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-3 font-mono text-xs leading-relaxed dark:bg-zinc-950">
                  {document.raw_text}
                </pre>
              </>
            ) : (
              <Empty icon={<FileText />}>No source document stored.</Empty>
            )}
          </Card>
          <PrivacyPanel
            candidateId={candidate.id}
            consent={candidate.talent_pool_consent}
            consentUpdatedAt={candidate.consent_updated_at}
            purgeAfter={document?.purged_at ? null : (document?.purge_after ?? null)}
          />
          <Card title="Best matching open jobs">
            {recommendations.length === 0 ? (
              <Empty>No open jobs.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {recommendations.map((r) => (
                  <li key={r.job_id} className="flex items-center justify-between gap-2">
                    <Link href={`/jobs/${r.job_id}`} className="hover:underline">
                      {r.title}
                    </Link>
                    <span className="flex items-center gap-2">
                      {!r.passed_knockouts && <Badge tone="red">criterion not met</Badge>}
                      <span className="tabular-nums">{r.overall_score.toFixed(1)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
