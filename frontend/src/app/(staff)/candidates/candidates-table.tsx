"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { FileUp, RotateCcw, Search, ShieldAlert, TriangleAlert, Users, CheckCircle2, SlidersHorizontal } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { Dialog, Pagination, Slider, SortHeader, usePaged, type SortState } from "@/components/interactive";
import { Badge, Button, Empty, Tooltip, cx, focusRing, inputClass, scoreTone, selectClass } from "@/components/ui";
import { formatDate } from "@/lib/format";
import type { EvaluationStatus } from "@/lib/insights";

import { UploadDropzone } from "./upload-dropzone";

export type CandidateRow = {
  id: string;
  name: string;
  title: string | null;
  applied: { jobId: string; title: string; stage: string }[];
  years: number | null;
  skills: string[];
  date: string;
  status: EvaluationStatus;
  unverified: number;
  score: { value: number; job: string; passed: boolean } | null;
  consent: boolean | null;
  /** Applied through the job board (the candidate owns the profile). */
  portal: boolean;
};

type SortKey = "name" | "years" | "date" | "status" | "score";

const STATUS: Record<EvaluationStatus, { label: string; tone: "green" | "amber" | "red"; icon: ReactNode }> = {
  verified: { label: "Verified", tone: "green", icon: <CheckCircle2 className="size-3" aria-hidden /> },
  to_review: { label: "To review", tone: "amber", icon: <TriangleAlert className="size-3" aria-hidden /> },
  flagged: { label: "Flagged", tone: "red", icon: <ShieldAlert className="size-3" aria-hidden /> },
};
const STATUS_ORDER: Record<EvaluationStatus, number> = { flagged: 0, to_review: 1, verified: 2 };

export function CandidatesTable({ rows, jobs, startWithUpload }: { rows: CandidateRow[]; jobs: { id: string; title: string }[]; startWithUpload: boolean }) {
  const [upload, setUpload] = useState(startWithUpload);
  const [showFilters, setShowFilters] = useState(true);
  const [query, setQuery] = useState("");
  const [job, setJob] = useState("all");
  const [skill, setSkill] = useState("");
  const [minYears, setMinYears] = useState(0);
  const [status, setStatus] = useState<EvaluationStatus | "all">("all");
  const [minScore, setMinScore] = useState(0);
  const [sort, setSort] = useState<SortState<SortKey>>({ key: "date", direction: "desc" });

  const allSkills = useMemo(() => [...new Set(rows.flatMap((r) => r.skills))].sort((a, b) => a.localeCompare(b)), [rows]);
  const active = job !== "all" || skill !== "" || minYears > 0 || status !== "all" || minScore > 0 || query !== "";

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const s = skill.trim().toLowerCase();
    const list = rows.filter((row) => {
      if (q && ![row.name, row.title, ...row.skills].join(" ").toLowerCase().includes(q)) return false;
      if (job === "pool" && row.applied.length > 0) return false;
      if (job !== "all" && job !== "pool" && !row.applied.some((a) => a.jobId === job)) return false;
      if (s && !row.skills.some((name) => name.toLowerCase() === s)) return false;
      if (minYears > 0 && (row.years ?? 0) < minYears) return false;
      if (status !== "all" && row.status !== status) return false;
      if (minScore > 0 && (row.score?.value ?? 0) < minScore) return false;
      return true;
    });
    const value = (row: CandidateRow): string | number => {
      switch (sort.key) {
        case "name":
          return row.name.toLowerCase();
        case "years":
          return row.years ?? -1;
        case "status":
          return STATUS_ORDER[row.status];
        case "score":
          return row.score?.value ?? -1;
        default:
          return row.date;
      }
    };
    return [...list].sort((a, b) => {
      const [x, y] = [value(a), value(b)];
      const order = x < y ? -1 : x > y ? 1 : 0;
      return sort.direction === "asc" ? order : -order;
    });
  }, [rows, query, job, skill, minYears, status, minScore, sort]);

  const { rows: pageRows, page, pageCount, setPage } = usePaged(filtered, 10);
  const reset = () => {
    setQuery("");
    setJob("all");
    setSkill("");
    setMinYears(0);
    setStatus("all");
    setMinScore(0);
    setPage(1);
  };
  const header = (label: string, key: SortKey, className?: string) => (
    <SortHeader label={label} sortKey={key} sort={sort} onSort={(next) => (setSort(next), setPage(1))} className={className} />
  );

  return (
    <div>
      <div className="space-y-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-52 flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
            <input
              value={query}
              onChange={(e) => (setQuery(e.target.value), setPage(1))}
              placeholder="Search name, title, skill…"
              aria-label="Search candidates"
              className={cx(inputClass, "pl-8")}
            />
          </div>
          <Button variant="secondary" size="md" icon={<SlidersHorizontal className="size-4" />} onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}>
            Filters
          </Button>
          {active && (
            <Button variant="ghost" icon={<RotateCcw className="size-4" />} onClick={reset}>
              Reset
            </Button>
          )}
          <span className="text-xs text-zinc-500">
            {filtered.length} of {rows.length}
          </span>
          <Button className="ml-auto" icon={<FileUp className="size-4" />} onClick={() => setUpload(true)}>
            Upload CVs
          </Button>
        </div>
        {showFilters && (
          <div className="grid gap-4 rounded-lg bg-zinc-50 p-3 sm:grid-cols-2 lg:grid-cols-5 dark:bg-zinc-900/60">
            <label className="text-xs">
              <span className="mb-1 block font-medium text-zinc-600 dark:text-zinc-300">Job</span>
              <select value={job} onChange={(e) => (setJob(e.target.value), setPage(1))} className={selectClass}>
                <option value="all">All candidates</option>
                <option value="pool">Talent pool only (no application)</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    Applied to {j.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block font-medium text-zinc-600 dark:text-zinc-300">Skill</span>
              <input list="skill-options" value={skill} onChange={(e) => (setSkill(e.target.value), setPage(1))} placeholder="Any skill" className={inputClass} />
              <datalist id="skill-options">
                {allSkills.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </label>
            <label className="text-xs">
              <span className="mb-1 block font-medium text-zinc-600 dark:text-zinc-300">Evaluation status</span>
              <select value={status} onChange={(e) => (setStatus(e.target.value as EvaluationStatus | "all"), setPage(1))} className={selectClass}>
                <option value="all">Any status</option>
                <option value="verified">Verified</option>
                <option value="to_review">To review</option>
                <option value="flagged">Flagged</option>
              </select>
            </label>
            <Slider label="Min. experience" value={minYears} max={15} step={1} format={(v) => (v ? `${v}+ yrs` : "Any")} onChange={(v) => (setMinYears(v), setPage(1))} />
            <Slider label="Min. match score" value={minScore} max={100} step={5} format={(v) => (v ? `≥ ${v}` : "Any")} onChange={(v) => (setMinScore(v), setPage(1))} />
          </div>
        )}
      </div>

      {filtered.length === 0 ? (
        <Empty
          icon={<Users />}
          title={rows.length ? "No candidate matches these filters" : "No candidate yet"}
          action={rows.length ? <Button variant="secondary" onClick={reset}>Reset filters</Button> : <Button onClick={() => setUpload(true)}>Upload CVs</Button>}
        >
          {rows.length ? "Loosen a filter to see more candidates." : "Upload CVs to build the talent pool."}
        </Empty>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[64rem] text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50/80 text-left text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60">
              <tr>
                {header("Candidate", "name")}
                <th scope="col" className="px-4 py-2.5 font-medium">
                  Applied position
                </th>
                {header("Experience", "years")}
                <th scope="col" className="px-4 py-2.5 font-medium">
                  Skills
                </th>
                {header("Date", "date")}
                {header("Evaluation", "status")}
                {header("Match score", "score")}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {pageRows.map((row) => (
                <tr key={row.id} className="group transition-colors hover:bg-brand-50/40 dark:hover:bg-zinc-800/40">
                  <td className="px-4 py-3">
                    <Link href={`/candidates/${row.id}`} className={cx("flex items-center gap-3 rounded-md", focusRing)}>
                      <Avatar id={row.id} name={row.name} />
                      <span className="min-w-0">
                        <span className="block truncate font-semibold group-hover:text-brand-700 dark:group-hover:text-brand-300">{row.name}</span>
                        <span className="block truncate text-xs text-zinc-500">
                          {row.portal && <span className="mr-1 font-medium text-sky-700 dark:text-sky-300">Job board ·</span>}
                          {row.title ?? "—"}
                        </span>
                      </span>
                    </Link>
                  </td>
                  <td className="max-w-52 px-4 py-3">
                    {row.applied.length === 0 ? (
                      <span className="text-xs text-zinc-500">{row.consent ? "Talent pool (consented)" : "Talent pool"}</span>
                    ) : (
                      <ul className="space-y-0.5">
                        {row.applied.slice(0, 2).map((a) => (
                          <li key={a.jobId} className="truncate">
                            <Link href={`/jobs/${a.jobId}/pipeline`} className="hover:underline">
                              {a.title}
                            </Link>
                            <span className="ml-1 text-xs text-zinc-500">· {a.stage}</span>
                          </li>
                        ))}
                        {row.applied.length > 2 && <li className="text-xs text-zinc-500">+{row.applied.length - 2} more</li>}
                      </ul>
                    )}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-zinc-600 dark:text-zinc-300">{row.years === null ? "—" : `${row.years} yrs`}</td>
                  <td className="px-4 py-3">
                    <div className="flex max-w-60 flex-wrap gap-1">
                      {row.skills.slice(0, 3).map((name) => (
                        <Badge key={name}>{name}</Badge>
                      ))}
                      {row.skills.length > 3 && <Badge tone="indigo">+{row.skills.length - 3}</Badge>}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-zinc-500">{formatDate(row.date)}</td>
                  <td className="px-4 py-3">
                    <Badge tone={STATUS[row.status].tone} title={row.unverified ? `${row.unverified} unverified item(s)` : undefined}>
                      {STATUS[row.status].icon} {STATUS[row.status].label}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {row.score ? (
                      <Tooltip content={`Best match: ${row.score.job}${row.score.passed ? "" : " (a mandatory criterion is not met)"} · deterministic engine`}>
                        <span className="flex items-center gap-2" tabIndex={0}>
                          <span className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                            <span className={cx("block h-full rounded-full", scoreTone(row.score.value))} style={{ width: `${row.score.value}%` }} />
                          </span>
                          <span className="w-8 text-right font-semibold tabular-nums">{Math.round(row.score.value)}</span>
                        </span>
                      </Tooltip>
                    ) : (
                      <span className="text-xs text-zinc-400">no open job</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination page={page} pageCount={pageCount} total={filtered.length} pageSize={10} onPage={setPage} />

      <Dialog open={upload} onClose={() => setUpload(false)} size="lg" title="Upload CVs" description="Each file is read by the AI, then every extracted item is checked against the document.">
        <UploadDropzone />
      </Dialog>
    </div>
  );
}
