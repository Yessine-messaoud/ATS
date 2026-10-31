"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition, type ReactNode } from "react";
import { Briefcase, CornerDownLeft, FileUp, LayoutDashboard, Loader2, MessageSquare, Search, ShieldCheck, User, Users } from "lucide-react";

import { searchEverything, type SearchHit } from "@/app/actions";

import { Kbd, cx } from "./ui";

type Entry = { key: string; title: string; subtitle?: string; href: string; icon: ReactNode; group: string };

const PAGES: Entry[] = [
  { key: "p-home", title: "Dashboard", href: "/", icon: <LayoutDashboard />, group: "Go to" },
  { key: "p-jobs", title: "Jobs", href: "/jobs", icon: <Briefcase />, group: "Go to" },
  { key: "p-new-job", title: "Create a job", subtitle: "Paste a job description", href: "/jobs?new=1", icon: <Briefcase />, group: "Go to" },
  { key: "p-candidates", title: "Candidates", href: "/candidates", icon: <Users />, group: "Go to" },
  { key: "p-upload", title: "Upload CVs", href: "/candidates?upload=1", icon: <FileUp />, group: "Go to" },
  { key: "p-assistant", title: "AI Assistant", href: "/assistant", icon: <MessageSquare />, group: "Go to" },
  { key: "p-eval", title: "CV Evaluation", href: "/evaluations", icon: <ShieldCheck />, group: "Go to" },
  { key: "p-analytics", title: "Analytics", href: "/analytics", icon: <LayoutDashboard />, group: "Go to" },
  { key: "p-settings", title: "Settings", href: "/settings", icon: <Briefcase />, group: "Go to" },
  { key: "p-audit", title: "Audit log", href: "/audit", icon: <ShieldCheck />, group: "Go to" },
];

function hitEntry(hit: SearchHit): Entry {
  return {
    key: `${hit.kind}-${hit.id}`,
    title: hit.title,
    subtitle: hit.subtitle,
    href: hit.href,
    icon: hit.kind === "job" ? <Briefcase /> : <User />,
    group: hit.kind === "job" ? "Jobs" : "Candidates",
  };
}

/** Ctrl+K / ⌘K: jump to any page, job or candidate (search covers names, titles and skills). */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  // Mounted only while open, so every opening starts with an empty search.
  return open ? <PaletteDialog onClose={() => onOpenChange(false)} /> : null;
}

function PaletteDialog({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const [searching, startSearch] = useTransition();

  useEffect(() => {
    if (!query.trim()) return;
    const timer = setTimeout(() => startSearch(async () => setHits(await searchEverything(query))), 150);
    return () => clearTimeout(timer);
  }, [query]);

  const entries = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pages = PAGES.filter((p) => !q || p.title.toLowerCase().includes(q));
    return [...(q ? hits.map(hitEntry) : []), ...pages];
  }, [query, hits]);

  const go = (entry: Entry | undefined) => {
    if (!entry) return;
    onClose();
    router.push(entry.href);
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-zinc-950/40 p-4 pt-[12vh] backdrop-blur-sm" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div className="flex items-center gap-2 border-b border-zinc-200 px-3 dark:border-zinc-800">
          {searching ? <Loader2 className="size-4 animate-spin text-zinc-400" /> : <Search className="size-4 text-zinc-400" />}
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(i + 1, entries.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                go(entries[active]);
              } else if (e.key === "Escape") {
                onClose();
              }
            }}
            placeholder="Search jobs, candidates, skills or pages…"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-zinc-400"
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-results"
            aria-activedescendant={entries[active] ? `palette-${entries[active].key}` : undefined}
          />
          <Kbd>Esc</Kbd>
        </div>
        <ul id="palette-results" role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
          {entries.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-zinc-500">{searching ? "Searching…" : "No match."}</li>
          )}
          {entries.map((entry, index) => {
            const header = entry.group !== lastGroup ? entry.group : null;
            lastGroup = entry.group;
            return (
              <li key={entry.key} role="presentation">
                {header && <p className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">{header}</p>}
                <button
                  id={`palette-${entry.key}`}
                  role="option"
                  aria-selected={index === active}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => go(entry)}
                  className={cx(
                    "flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm",
                    index === active ? "bg-brand-50 text-brand-900 dark:bg-brand-950 dark:text-brand-100" : "",
                  )}
                >
                  <span className="text-zinc-400 [&>svg]:size-4">{entry.icon}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{entry.title}</span>
                    {entry.subtitle && <span className="block truncate text-xs text-zinc-500">{entry.subtitle}</span>}
                  </span>
                  {index === active && <CornerDownLeft className="size-3.5 text-zinc-400" aria-hidden />}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
