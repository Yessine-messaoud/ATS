"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { Archive, ClipboardCheck, KanbanSquare, ListOrdered, MapPin, MoreHorizontal, RotateCcw, Search, SlidersHorizontal, Briefcase } from "lucide-react";

import { setJobStatus } from "@/app/actions";
import { Menu, Pagination, SortHeader, usePaged, type SortState } from "@/components/interactive";
import { CompanyMark, JobIcon } from "@/components/job-visuals";
import { useToast } from "@/components/toaster";
import { Badge, Empty, JOB_STATUS, JobStatusBadge, cx, focusRing, inputClass, jobStatus, selectClass, type JobStatus } from "@/components/ui";
import type { Job } from "@/lib/api";
import { CONTRACT_TYPES } from "@/lib/enums";

export type JobRow = { job: Job; applications: number; shortlisted: number };
type SortKey = "title" | "company" | "location" | "applications" | "status" | "created";

const STATUS_ORDER: Record<JobStatus, number> = { pending: 0, validated: 1, draft: 2, closed: 3 };
const pretty = (value: string | null | undefined) => (value ? value.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "—");

function RowActions({ job }: { job: Job }) {
  const router = useRouter();
  const notify = useToast();
  const [, startTransition] = useTransition();
  const open = job.status === "open";
  return (
    <Menu
      label={`Actions for ${job.profile.title}`}
      trigger={
        <span className="flex size-8 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100">
          <MoreHorizontal className="size-4" />
        </span>
      }
      items={[
        { label: "Ranking", href: `/jobs/${job.id}`, icon: <ListOrdered /> },
        { label: job.requirements_validated ? "Edit requirements" : "Review & validate", href: `/jobs/${job.id}/requirements`, icon: <ClipboardCheck /> },
        { label: "Pipeline", href: `/jobs/${job.id}/pipeline`, icon: <KanbanSquare /> },
        { label: "Scoring weights", href: `/jobs/${job.id}/weights`, icon: <SlidersHorizontal /> },
        {
          label: open ? "Close job" : "Reopen job",
          icon: open ? <Archive /> : <RotateCcw />,
          danger: open,
          onSelect: () =>
            startTransition(async () => {
              await setJobStatus(job.id, open ? "closed" : "open");
              notify(open ? `${job.profile.title} closed.` : `${job.profile.title} reopened.`);
              router.refresh();
            }),
        },
      ]}
    />
  );
}

/** Jobs table with search, filters, sorting and pagination (all client-side over the loaded jobs). */
export function JobsTable({ rows, pageSize = 8, compact = false }: { rows: JobRow[]; pageSize?: number; compact?: boolean }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<JobStatus | "all">("all");
  const [contract, setContract] = useState<string>("all");
  const [sort, setSort] = useState<SortState<SortKey>>({ key: "created", direction: "desc" });

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = rows.filter(({ job }) => {
      if (status !== "all" && jobStatus(job) !== status) return false;
      if (contract !== "all" && job.profile.contract_type !== contract) return false;
      if (!q) return true;
      return [job.profile.title, job.profile.company, job.profile.location?.city, ...(job.profile.skill_requirements ?? []).map((s) => s.name)]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
    const value = ({ job, applications }: JobRow): string | number => {
      switch (sort.key) {
        case "title":
          return job.profile.title.toLowerCase();
        case "company":
          return (job.profile.company ?? "~").toLowerCase();
        case "location":
          return (job.profile.location?.city ?? "~").toLowerCase();
        case "applications":
          return applications;
        case "status":
          return STATUS_ORDER[jobStatus(job)];
        default:
          return job.created_at;
      }
    };
    return [...list].sort((a, b) => {
      const [x, y] = [value(a), value(b)];
      const order = x < y ? -1 : x > y ? 1 : 0;
      return sort.direction === "asc" ? order : -order;
    });
  }, [rows, query, status, contract, sort]);

  const { rows: pageRows, page, pageCount, setPage } = usePaged(filtered, pageSize);
  const contracts = CONTRACT_TYPES.filter((type) => rows.some(({ job }) => job.profile.contract_type === type));
  const header = (label: string, key: SortKey, className?: string) => (
    <SortHeader label={label} sortKey={key} sort={sort} onSort={(next) => (setSort(next), setPage(1))} className={className} />
  );

  return (
    <div>
      {!compact && (
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div className="relative min-w-52 flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <input
              value={query}
              onChange={(e) => (setQuery(e.target.value), setPage(1))}
              placeholder="Search title, company, city, skill…"
              aria-label="Search jobs"
              className={cx(inputClass, "pl-8")}
            />
          </div>
          <select aria-label="Filter by status" value={status} onChange={(e) => (setStatus(e.target.value as JobStatus | "all"), setPage(1))} className={cx(selectClass, "w-auto")}>
            <option value="all">All statuses</option>
            {(["validated", "pending", "closed"] as const).map((key) => (
              <option key={key} value={key}>
                {JOB_STATUS[key].label}
              </option>
            ))}
          </select>
          <select aria-label="Filter by contract" value={contract} onChange={(e) => (setContract(e.target.value), setPage(1))} className={cx(selectClass, "w-auto")}>
            <option value="all">All contracts</option>
            {contracts.map((type) => (
              <option key={type} value={type}>
                {pretty(type)}
              </option>
            ))}
          </select>
          <span className="ml-auto text-xs text-zinc-500">
            {filtered.length} of {rows.length} jobs
          </span>
        </div>
      )}

      {filtered.length === 0 ? (
        <Empty icon={<Briefcase />} title={rows.length ? "No job matches these filters" : "No job yet"}>
          {rows.length ? "Change the search or the filters." : "Create a job by pasting its description."}
        </Empty>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[60rem] text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50/80 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60">
              <tr>
                {header("Job title", "title")}
                {header("Company", "company")}
                {header("Location", "location")}
                <th scope="col" className="px-4 py-2.5 font-medium">
                  Contract
                </th>
                <th scope="col" className="px-4 py-2.5 font-medium">
                  Required skills
                </th>
                {header("Applications", "applications", "text-right")}
                {header("Status", "status")}
                <th scope="col" className="w-12 px-4 py-2.5">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {pageRows.map(({ job, applications, shortlisted }) => {
                const required = (job.profile.skill_requirements ?? []).filter((s) => s.requirement === "required");
                return (
                  <tr key={job.id} className="group transition-colors hover:bg-brand-50/40 dark:hover:bg-zinc-800/40">
                    <td className="px-4 py-3">
                      <Link href={`/jobs/${job.id}`} className={cx("flex items-center gap-3 rounded-md", focusRing)}>
                        <JobIcon title={job.profile.title} size="sm" />
                        <span className="min-w-0">
                          <span className="block truncate font-semibold group-hover:text-brand-700 dark:group-hover:text-brand-300">{job.profile.title}</span>
                          {job.profile.seniority && <span className="block text-xs text-zinc-500">{pretty(job.profile.seniority)}</span>}
                        </span>
                      </Link>
                    </td>
                    <td className="max-w-40 px-4 py-3 text-zinc-600 dark:text-zinc-300">
                      <CompanyMark name={job.profile.company} />
                    </td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-300">
                      <span className="flex items-center gap-1">
                        <MapPin className="size-3.5 text-zinc-400" aria-hidden />
                        {job.profile.location?.city ?? "—"}
                      </span>
                      {job.profile.work_mode && <span className="text-xs text-zinc-500">{pretty(job.profile.work_mode)}</span>}
                    </td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-300">{pretty(job.profile.contract_type)}</td>
                    <td className="px-4 py-3">
                      <div className="flex max-w-56 flex-wrap gap-1">
                        {required.slice(0, 3).map((s) => (
                          <Badge key={s.name}>{s.name}</Badge>
                        ))}
                        {required.length > 3 && <Badge tone="indigo">+{required.length - 3}</Badge>}
                        {required.length === 0 && <span className="text-xs text-zinc-400">none</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className="font-semibold">{applications}</span>
                      {shortlisted > 0 && <span className="block text-xs text-zinc-500">{shortlisted} shortlisted</span>}
                    </td>
                    <td className="px-4 py-3">
                      <JobStatusBadge status={jobStatus(job)} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <RowActions job={job} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {!compact && <Pagination page={page} pageCount={pageCount} total={filtered.length} pageSize={pageSize} onPage={setPage} />}
    </div>
  );
}
