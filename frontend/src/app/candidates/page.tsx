import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Card, Empty, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { FLAG_LABELS } from "@/lib/enums";

import { UploadDropzone } from "./upload-dropzone";

export const metadata: Metadata = { title: "Candidates" };

const SECURITY_FLAGS = new Set(["hidden_text", "possible_prompt_injection"]);

export default async function CandidatesPage(props: PageProps<"/candidates">) {
  const [candidates, { erased }] = await Promise.all([api.candidates(), props.searchParams]);

  return (
    <div className="space-y-4">
    {erased && (
      <Notice tone="green">The candidate and all their personal data were erased. The erasure is recorded in the audit log.</Notice>
    )}
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <Card title={`Candidates (${candidates.length})`}>
        {candidates.length === 0 ? (
          <Empty>No candidates yet. Upload CVs to get started.</Empty>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-zinc-500">
              <tr>
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Title</th>
                <th className="pb-2 font-medium">Review</th>
                <th className="pb-2 font-medium">Added</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {candidates.map((candidate) => {
                const flags = (candidate.extraction.document_flags as string[] | undefined) ?? [];
                const evidence = candidate.extraction.evidence as { unverified?: number } | undefined;
                return (
                  <tr key={candidate.id}>
                    <td className="py-2">
                      <Link href={`/candidates/${candidate.id}`} className="font-medium hover:underline">
                        {candidate.profile.identity?.full_name ?? "Unnamed candidate"}
                      </Link>
                    </td>
                    <td className="py-2 text-zinc-600 dark:text-zinc-400">{candidate.profile.professional_title ?? "—"}</td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {flags
                          .filter((flag) => SECURITY_FLAGS.has(flag))
                          .map((flag) => (
                            <Badge key={flag} tone="red">
                              {FLAG_LABELS[flag] ?? flag}
                            </Badge>
                          ))}
                        {evidence?.unverified ? (
                          <Badge tone="amber">{evidence.unverified} unverified item(s)</Badge>
                        ) : (
                          <Badge tone="green">evidence checked</Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-2 text-zinc-500">{new Date(candidate.created_at).toLocaleDateString("en-GB")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
      <Card title="Upload CVs">
        <UploadDropzone />
      </Card>
    </div>
    </div>
  );
}
