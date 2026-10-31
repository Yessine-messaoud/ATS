import Link from "next/link";
import { AlertTriangle, CircleSlash, Info, Users } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { BlindToggle, isBlind } from "@/components/blind-toggle";
import { Badge, ButtonLink, Card, Empty, Notice, STATUS_TONE, ScoreBar, cx, focusRing } from "@/components/ui";
import { api, type RankedCandidate } from "@/lib/api";

import { RankingRowActions } from "./ranking-row-actions";

export default async function RankingPage(props: PageProps<"/jobs/[id]">) {
  const { id } = await props.params;
  const blind = isBlind((await props.searchParams).blind);
  const [ranking, applications] = await Promise.all([api.ranking(id, blind), api.applications(id, false)]);
  const inPipeline = new Set(applications.map((a) => a.candidate_id));

  return (
    <div className="space-y-5">
      {!ranking.requirements_validated && (
        <Notice icon={<AlertTriangle />}>
          These scores use requirements that have not been validated yet.{" "}
          <Link href={`/jobs/${id}/requirements`} className="font-medium underline">
            Review the requirements
          </Link>{" "}
          before relying on the ranking.
        </Notice>
      )}
      <Card
        title="Meeting every mandatory criterion"
        description={`${ranking.ranked.length} candidate${ranking.ranked.length === 1 ? "" : "s"}, best score first`}
        actions={<BlindToggle href={`/jobs/${id}`} blind={blind} />}
        flush
      >
        <RankingList rows={ranking.ranked} jobId={id} inPipeline={inPipeline} blind={blind} />
      </Card>
      <Card
        title="A mandatory criterion is not met"
        description="Listed separately, never hidden: the reason may be missing information rather than a real gap."
        flush
      >
        <RankingList rows={ranking.knocked_out} jobId={id} inPipeline={inPipeline} blind={blind} knockedOut />
      </Card>
      <p className="flex items-start gap-1.5 text-xs text-zinc-500">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Engine {ranking.engine_version}.{" "}
          {ranking.retrieval_mode === "all"
            ? `All ${ranking.pool_size} candidates scored.`
            : `${ranking.scored} of ${ranking.pool_size} candidates shortlisted by hybrid search, then scored.`}{" "}
          Scores are computed deterministically from the requirements; no AI is involved and the recruiter makes every decision.
        </span>
      </p>
    </div>
  );
}

function RankingList({
  rows,
  jobId,
  inPipeline,
  blind,
  knockedOut,
}: {
  rows: RankedCandidate[];
  jobId: string;
  inPipeline: Set<string>;
  blind: boolean;
  knockedOut?: boolean;
}) {
  if (rows.length === 0) {
    return knockedOut ? (
      <Empty icon={<CircleSlash />}>No candidate is excluded by a mandatory criterion.</Empty>
    ) : (
      <Empty
        icon={<Users />}
        title="No candidate meets every mandatory criterion yet"
        action={<ButtonLink href="/candidates?upload=1">Upload CVs</ButtonLink>}
      />
    );
  }
  return (
    <div>
      <div className="hidden grid-cols-[2rem_minmax(10rem,1.2fr)_8rem_minmax(10rem,2fr)_minmax(8rem,1.2fr)_auto] gap-4 border-b border-zinc-200 bg-zinc-50 px-4 py-2 text-xs font-medium text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 lg:grid">
        <span>#</span>
        <span>Candidate</span>
        <span>Score</span>
        <span>Required skills</span>
        <span>To check</span>
        <span className="sr-only">Actions</span>
      </div>
      <ol className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {rows.map((row, index) => (
          <li
            key={row.candidate_id}
            className="grid grid-cols-[2rem_1fr] items-center gap-x-4 gap-y-2 px-4 py-3 lg:grid-cols-[2rem_minmax(10rem,1.2fr)_8rem_minmax(10rem,2fr)_minmax(8rem,1.2fr)_auto]"
          >
            <span className="text-sm tabular-nums text-zinc-400">{index + 1}</span>
            <div className="flex min-w-0 items-center gap-2.5">
              {!blind && <Avatar id={row.candidate_id} name={row.display_name} size="sm" />}
              {blind ? (
                <span className="truncate font-medium">{row.display_name}</span>
              ) : (
                <Link href={`/candidates/${row.candidate_id}`} className={cx("truncate rounded font-medium hover:underline", focusRing)}>
                  {row.display_name}
                </Link>
              )}
            </div>
            <div className="col-start-2 lg:col-start-auto">
              <ScoreBar score={row.overall_score} />
            </div>
            <div className="col-start-2 flex flex-wrap gap-1 lg:col-start-auto">
              {row.matched_required.map((skill) => (
                <Badge key={skill} tone="green">
                  {skill}
                </Badge>
              ))}
              {row.missing_required.map((skill) => (
                <Badge key={skill} tone="red" title="missing required skill">
                  <span aria-hidden>✗</span> {skill}
                </Badge>
              ))}
            </div>
            <div className="col-start-2 flex flex-wrap gap-1 lg:col-start-auto">
              {row.knockouts.length === 0 ? (
                <span className="hidden text-xs text-zinc-400 lg:inline">—</span>
              ) : (
                row.knockouts.map((k) => (
                  <Badge key={k.factor_id} tone={STATUS_TONE[k.status]} title={k.detail}>
                    {k.status}: {k.criterion}
                  </Badge>
                ))
              )}
            </div>
            <div className="col-start-2 lg:col-start-auto">
              <RankingRowActions jobId={jobId} candidateId={row.candidate_id} inPipeline={inPipeline.has(row.candidate_id)} />
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
