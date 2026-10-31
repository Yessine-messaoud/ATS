import type { Metadata } from "next";
import Link from "next/link";
import { Building2 } from "lucide-react";

import { Badge, Card, Empty, PageHeader, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { requireUser } from "@/lib/session";

import { CompanyActions } from "./company-actions";

export const metadata: Metadata = { title: "Companies" };

const STATUS = {
  active: { tone: "green", label: "Approved" },
  pending: { tone: "amber", label: "Pending" },
  suspended: { tone: "red", label: "Suspended" },
} as const;
const FILTERS = [
  { value: undefined, label: "All" },
  { value: "pending", label: "Pending" },
  { value: "active", label: "Approved" },
  { value: "suspended", label: "Suspended" },
] as const;

export default async function CompaniesPage({ searchParams }: PageProps<"/admin/companies">) {
  await requireUser(["admin"], "/admin/companies");
  const { status } = await searchParams;
  const filter = typeof status === "string" && status in STATUS ? status : undefined;
  const companies = await api.adminOrganizations(filter);

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: "Administration", href: "/admin" }, { label: "Companies" }]}
        title="Companies"
        description="Approve new companies before their jobs reach the job board; suspend one to sign its recruiters out and hide its jobs."
      />
      <Card flush>
        <div className="flex flex-wrap gap-1 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800" role="tablist" aria-label="Filter by status">
          {FILTERS.map(({ value, label }) => (
            <Link
              key={label}
              href={value ? `/admin/companies?status=${value}` : "/admin/companies"}
              role="tab"
              aria-selected={filter === value}
              className={cx(
                "rounded-md px-3 py-1.5 text-sm",
                filter === value ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-200" : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800",
              )}
            >
              {label}
            </Link>
          ))}
        </div>
        {companies.length === 0 ? (
          <Empty icon={<Building2 />} title="No company">
            Companies sign up from the job board, or appear when you add a recruiter.
          </Empty>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[48rem] text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50/80 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Company</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Recruiters</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Jobs (open)</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Applications</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Since</th>
                  <th scope="col" className="px-4 py-2.5"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {companies.map((company) => (
                  <tr key={company.id}>
                    <td className="px-4 py-3">
                      <Link href={`/admin/users?organization_id=${company.id}`} className="font-medium hover:underline">
                        {company.name}
                      </Link>
                      <span className="block text-xs text-zinc-500">{[company.industry, company.city].filter(Boolean).join(" · ") || "No profile yet"}</span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS[company.status].tone}>{STATUS[company.status].label}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{company.recruiters}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {company.jobs} <span className="text-zinc-500">({company.open_jobs})</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{company.applications}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-500">{formatDate(company.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <CompanyActions organization={company} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
