import type { Metadata } from "next";
import Link from "next/link";

import { ShieldCheck } from "lucide-react";

import { Badge, Button, Card, Empty, PageHeader, inputClass, type Tone } from "@/components/ui";
import { api } from "@/lib/api";
import { actionLabel, timeAgo } from "@/lib/format";

export const metadata: Metadata = { title: "Audit log" };

const ACTION_GROUPS = [
  ["", "All actions"],
  ["candidate.", "Candidates"],
  ["job.", "Jobs"],
  ["application.", "Pipeline decisions"],
  ["match.", "Scores"],
  ["document.", "Documents"],
] as const;

function tone(action: string): Tone {
  if (action.endsWith("erased") || action.endsWith("purged")) return "red";
  if (action.startsWith("application.")) return "blue";
  if (action.startsWith("match.")) return "green";
  return "neutral";
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value || undefined;
}

/** Who did what, when: every recruiter decision, AI output, correction and privacy operation. Read-only. */
export default async function AuditPage(props: PageProps<"/audit">) {
  const params = await props.searchParams;
  const filters = {
    entity_id: first(params.entity_id),
    action: first(params.action),
    actor: first(params.actor),
    before: first(params.before),
    limit: "100",
  };
  const entries = await api.audit(filters);
  const older = entries.length === 100 ? entries[entries.length - 1].created_at : null;
  const keep = (extra: Record<string, string>) => {
    const kept = Object.entries(filters).filter(
      (entry): entry is [string, string] => !!entry[1] && entry[0] !== "limit" && entry[0] !== "before",
    );
    return `/audit?${new URLSearchParams({ ...Object.fromEntries(kept), ...extra })}`;
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Audit log"
        description="Every recruiter decision, automated score, profile correction and privacy operation, newest first. Entries hold ids, not personal data."
      />
      <form className="flex flex-wrap items-end gap-2 text-sm" action="/audit">
        <label className="text-xs text-zinc-500">
          Record id
          <input name="entity_id" defaultValue={filters.entity_id} placeholder="candidate, job or application id" className={`${inputClass} sm:w-80`} />
        </label>
        <label className="text-xs text-zinc-500">
          Actions
          <select name="action" defaultValue={filters.action ?? ""} className={inputClass}>
            {ACTION_GROUPS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          Actor
          <input name="actor" defaultValue={filters.actor} placeholder="recruiter, system…" className={`${inputClass} sm:w-44`} />
        </label>
        <Button type="submit">Filter</Button>
        <Link href="/audit" className="text-xs underline">
          Reset
        </Link>
      </form>
      <Card>
        {entries.length === 0 ? (
          <Empty icon={<ShieldCheck />} title="No entries match">Change the filters or reset them.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-zinc-500">
                <tr>
                  <th className="pb-2 font-medium">When</th>
                  <th className="pb-2 font-medium">Actor</th>
                  <th className="pb-2 font-medium">Action</th>
                  <th className="pb-2 font-medium">Record</th>
                  <th className="pb-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 align-top dark:divide-zinc-800">
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="whitespace-nowrap py-2 pr-3" title={new Date(entry.created_at).toLocaleString("en-GB")}>
                      {timeAgo(entry.created_at)}
                    </td>
                    <td className="py-2 pr-3">{entry.actor}</td>
                    <td className="py-2 pr-3">
                      <Badge tone={tone(entry.action)} title={entry.action}>
                        {actionLabel(entry.action)}
                      </Badge>
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {entry.entity_id ? (
                        <Link href={keep({ entity_id: entry.entity_id })} className="hover:underline">
                          {entry.entity_type}:{entry.entity_id.slice(0, 8)}
                        </Link>
                      ) : (
                        entry.entity_type
                      )}
                    </td>
                    <td className="py-2 font-mono text-xs text-zinc-600 dark:text-zinc-400">
                      {Object.keys(entry.details).length ? JSON.stringify(entry.details) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {older && (
          <div className="mt-3">
            <Link href={keep({ before: older })} className="text-xs underline">
              Older entries →
            </Link>
          </div>
        )}
      </Card>
    </div>
  );
}
