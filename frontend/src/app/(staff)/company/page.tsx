import type { Metadata } from "next";
import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { Badge, Card, Notice, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

import { CompanyForm, TeamList } from "./company-forms";

export const metadata: Metadata = { title: "Company" };

const STATUS = {
  active: { tone: "green", label: "Approved" },
  pending: { tone: "amber", label: "Awaiting approval" },
  suspended: { tone: "red", label: "Suspended" },
} as const;

export default async function CompanyPage() {
  const user = await requireUser(["recruiter"], "/company");
  const [organization, members] = await Promise.all([api.organization(), api.members()]);
  const status = STATUS[organization.status];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        title={organization.name}
        badges={<Badge tone={status.tone}>{status.label}</Badge>}
        description="Your company profile, shown to candidates on the job board, and the recruiters who work with you."
        actions={
          organization.status === "active" && (
            <Link href={`/careers?company=${organization.id}`} className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline dark:text-brand-300">
              View on the job board <ExternalLink className="size-3.5" aria-hidden />
            </Link>
          )
        }
      />
      {organization.status === "pending" && (
        <Notice tone="amber">A platform administrator reviews new companies. Your jobs appear on the job board once the company is approved.</Notice>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card title="Company profile" description="Candidates see this next to each of your jobs.">
          <CompanyForm organization={organization} />
        </Card>
        <Card flush title="Team" description={`${members.length} recruiter${members.length === 1 ? "" : "s"}`}>
          <TeamList members={members} selfId={user.id} />
        </Card>
      </div>
    </div>
  );
}
