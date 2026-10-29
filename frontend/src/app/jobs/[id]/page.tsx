import Link from "next/link";

import { BlindToggle, isBlind } from "@/components/blind-toggle";
import { Badge, Card, Empty, Notice, STATUS_TONE, ScoreBar } from "@/components/ui";
import { api, type RankedCandidate } from "@/lib/api";

import { RankingRowActions } from "./ranking-row-actions";

export default async function RankingPage(props: PageProps<"/jobs/[id]">) {
  const { id } = await props.params;
  const blind = isBlind((await props.searchParams).blind);
  const [ranking, applications] = await Promise.all([api.ranking(id, blind), api.applications(id, false)]);
  const inPipeline = new Set(applications.map((a) => a.candidate_id));

  return (
    <div className="space-y-4">
      {!ranking.requirements_validated && (
        <Notice>
          These scores use requirements that have not been validated yet.{" "}
          <Link href={`/jobs/${id}/requirements`} className="font-medium underline">
            Review the requirements
          </Link>{" "}
          before relying on the ranking.
        </Notice>
      )}
      <Card
        title={`Ranked candidates (${ranking.ranked.length})`}
        actions={<BlindToggle href={`/jobs/${id}`} blind={blind} />}
      >
        <RankingTable rows={ranking.ranked} jobId={id} inPipeline={inPipeline} blind={blind} />
      </Card>
      <Card title={`Not meeting a mandatory criterion (${ranking.knocked_out.length})`}>
        <p className="mb-3 text-sm text-zinc-500">
          Listed separately, not hidden: check the reason; it may be missing information rather than a real gap.
        </p>
        <RankingTable rows={ranking.knocked_out} jobId={id} inPipeline={inPipeline} blind={blind} />
      </Card>
      <p className="text-xs text-zinc-500">
        Engine {ranking.engine_version}. Scores are computed deterministically from the validated requirements; the
        recruiter makes every decision.
      </p>
    </div>
  );
}

function RankingTable({
  rows,
  jobId,
  inPipeline,
  blind,
}: {
  rows: RankedCandidate[];
  jobId: string;
  inPipeline: Set<string>;
  blind: boolean;
}) {
  if (rows.length === 0) return <Empty>No candidates.</Empty>;
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs text-zinc-500">
        <tr>
          <th className="w-8 pb-2 font-medium">#</th>
          <th className="pb-2 font-medium">Candidate</th>
          <th className="pb-2 font-medium">Score</th>
          <th className="pb-2 font-medium">Required skills</th>
          <th className="pb-2 font-medium">To check</th>
          <th className="pb-2" />
        </tr>
      </thead>
      <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {rows.map((row, index) => (
          <tr key={row.candidate_id} className="align-top">
            <td className="py-2 text-zinc-500">{index + 1}</td>
            <td className="py-2 font-medium">
              {blind ? (
                row.display_name
              ) : (
                <Link href={`/candidates/${row.candidate_id}`} className="hover:underline">
                  {row.display_name}
                </Link>
              )}
            </td>
            <td className="py-2">
              <ScoreBar score={row.overall_score} />
            </td>
            <td className="py-2">
              <div className="flex flex-wrap gap-1">
                {row.matched_required.map((skill) => (
                  <Badge key={skill} tone="green">
                    {skill}
                  </Badge>
                ))}
                {row.missing_required.map((skill) => (
                  <Badge key={skill} tone="red" title="missing required skill">
                    ✗ {skill}
                  </Badge>
                ))}
              </div>
            </td>
            <td className="py-2">
              <div className="flex flex-col gap-1">
                {row.knockouts.map((k) => (
                  <Badge key={k.factor_id} tone={STATUS_TONE[k.status]} title={k.detail}>
                    {k.status}: {k.criterion}
                  </Badge>
                ))}
              </div>
            </td>
            <td className="py-2 text-right">
              <RankingRowActions jobId={jobId} candidateId={row.candidate_id} inPipeline={inPipeline.has(row.candidate_id)} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
