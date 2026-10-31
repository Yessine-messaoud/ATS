"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowDownUp, FileUp, Search, ShieldAlert, Users, X } from "lucide-react";

import { Avatar } from "@/components/avatar";
import { Badge, Button, Card, Empty, cx, focusRing, inputClass } from "@/components/ui";
import type { Candidate } from "@/lib/api";
import { formatDate } from "@/lib/format";

import { UploadDropzone } from "./upload-dropzone";

const SECURITY_FLAGS = new Set(["hidden_text", "possible_prompt_injection"]);

function facts(candidate: Candidate) {
  const flags = (candidate.extraction.document_flags as string[] | undefined) ?? [];
  const unverified = (candidate.extraction.evidence as { unverified?: number } | undefined)?.unverified ?? 0;
  return { security: flags.some((f) => SECURITY_FLAGS.has(f)), unverified };
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "review", label: "Needs review" },
  { key: "security", label: "Security flag" },
  { key: "consent", label: "Talent pool" },
] as const;
type Filter = (typeof FILTERS)[number]["key"];

function keep(candidate: Candidate, filter: Filter): boolean {
  const { security, unverified } = facts(candidate);
  if (filter === "review") return security || unverified > 0;
  if (filter === "security") return security;
  if (filter === "consent") return candidate.talent_pool_consent === true;
  return true;
}

type Sort = "newest" | "name";

export function CandidateBoard({ candidates, startWithUpload }: { candidates: Candidate[]; startWithUpload: boolean }) {
  const [showUpload, setShowUpload] = useState(startWithUpload);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("newest");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = candidates
      .filter((c) => keep(c, filter))
      .filter(
        (c) =>
          !q ||
          [c.profile.identity?.full_name, c.profile.professional_title, ...(c.profile.skills ?? []).map((s) => s.name)]
            .join(" ")
            .toLowerCase()
            .includes(q),
      );
    return sort === "name"
      ? list.sort((a, b) => (a.profile.identity?.full_name ?? "").localeCompare(b.profile.identity?.full_name ?? ""))
      : list.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [candidates, query, filter, sort]);

  return (
    <div className="space-y-4">
      {showUpload && (
        <Card
          title="Upload CVs"
          description="Each file is read by the AI, then every extracted item is checked against the document."
          actions={
            candidates.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setShowUpload(false)} icon={<X className="size-4" />}>
                Close
              </Button>
            )
          }
        >
          <UploadDropzone />
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400" aria-hidden />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, title, skill…"
            aria-label="Search candidates"
            className={cx(inputClass, "pl-8")}
          />
        </div>
        <div role="tablist" aria-label="Filter candidates" className="flex flex-wrap rounded-lg border border-zinc-200 bg-white p-0.5 dark:border-zinc-800 dark:bg-zinc-900">
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              role="tab"
              aria-selected={filter === key}
              onClick={() => setFilter(key)}
              className={cx(
                "rounded-md px-2.5 py-1 text-xs font-medium",
                filter === key ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300" : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100",
                focusRing,
              )}
            >
              {label} <span className="tabular-nums opacity-70">{candidates.filter((c) => keep(c, key)).length}</span>
            </button>
          ))}
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={<ArrowDownUp className="size-3.5" />}
          onClick={() => setSort(sort === "newest" ? "name" : "newest")}
          title="Change the order"
        >
          {sort === "newest" ? "Newest first" : "By name"}
        </Button>
        {!showUpload && (
          <Button className="ml-auto" onClick={() => setShowUpload(true)} icon={<FileUp className="size-4" />}>
            Upload CVs
          </Button>
        )}
      </div>

      <Card flush>
        {visible.length === 0 ? (
          <Empty icon={<Users />} title={candidates.length ? "No candidate matches" : "No candidate yet"}>
            {candidates.length ? "Change the search or the filter." : "Upload CVs to build the talent pool."}
          </Empty>
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {visible.map((candidate) => {
              const { security, unverified } = facts(candidate);
              const name = candidate.profile.identity?.full_name ?? "Unnamed candidate";
              const skills = candidate.profile.skills ?? [];
              return (
                <li key={candidate.id}>
                  <Link
                    href={`/candidates/${candidate.id}`}
                    className={cx("flex items-center gap-3 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50", focusRing)}
                  >
                    <Avatar id={candidate.id} name={name} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2">
                        <span className="font-medium">{name}</span>
                        <span className="text-sm text-zinc-500">{candidate.profile.professional_title ?? ""}</span>
                      </div>
                      <div className="mt-1 hidden flex-wrap gap-1 sm:flex">
                        {skills.slice(0, 6).map((s) => (
                          <Badge key={s.name}>{s.name}</Badge>
                        ))}
                        {skills.length > 6 && <Badge>+{skills.length - 6}</Badge>}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <div className="flex flex-wrap justify-end gap-1">
                        {security && (
                          <Badge tone="red">
                            <ShieldAlert className="size-3" aria-hidden /> security flag
                          </Badge>
                        )}
                        {unverified > 0 && (
                          <Badge tone="amber">
                            <AlertTriangle className="size-3" aria-hidden /> {unverified} to verify
                          </Badge>
                        )}
                        {candidate.talent_pool_consent && <Badge tone="indigo">talent pool</Badge>}
                      </div>
                      <span className="text-xs text-zinc-400">{formatDate(candidate.created_at)}</span>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
