import type { Metadata } from "next";
import { CheckCircle2 } from "lucide-react";

import { Notice, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

import { CandidateBoard } from "./candidate-board";

export const metadata: Metadata = { title: "Candidates" };

export default async function CandidatesPage(props: PageProps<"/candidates">) {
  const [candidates, params] = await Promise.all([api.candidates(), props.searchParams]);

  return (
    <div className="space-y-6">
      <PageHeader title="Candidates" description="The talent pool. Every extracted item is checked against the source document." />
      {params.erased && (
        <Notice tone="green" icon={<CheckCircle2 />}>
          The candidate and all their personal data were erased. The erasure is recorded in the audit log.
        </Notice>
      )}
      <CandidateBoard candidates={candidates} startWithUpload={params.upload === "1" || candidates.length === 0} />
    </div>
  );
}
