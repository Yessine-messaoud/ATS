import { BarChart3, BrainCircuit, Briefcase, Code2, Database, Megaphone, Palette, Server, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cx } from "./ui";

const FAMILIES: { pattern: RegExp; icon: LucideIcon; tone: string }[] = [
  { pattern: /machine learning|\bml\b|\bai\b|\bia\b|data scien|deep learning|nlp|vision/i, icon: BrainCircuit, tone: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300" },
  { pattern: /data engineer|données|data|etl|big data/i, icon: Database, tone: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" },
  { pattern: /devops|sre|cloud|infra|platform|système|system/i, icon: Server, tone: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" },
  { pattern: /\bbi\b|analyst|analyste|business intelligence|reporting/i, icon: BarChart3, tone: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300" },
  { pattern: /security|sécurité|cyber/i, icon: ShieldCheck, tone: "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300" },
  { pattern: /design|ux|ui\b/i, icon: Palette, tone: "bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300" },
  { pattern: /marketing|sales|commercial|vente/i, icon: Megaphone, tone: "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300" },
  { pattern: /develop|développ|engineer|ingénieur|full.?stack|front|back|software|logiciel/i, icon: Code2, tone: "bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300" },
];

/** Icon for the job family, inferred from the title (a display hint only; not stored or used in scoring). */
export function JobIcon({ title, size = "md" }: { title: string; size?: "sm" | "md" }) {
  const family = FAMILIES.find((f) => f.pattern.test(title));
  const Icon = family?.icon ?? Briefcase;
  return (
    <span
      aria-hidden
      className={cx(
        "flex shrink-0 items-center justify-center rounded-lg",
        size === "sm" ? "size-8 [&>svg]:size-4" : "size-10 [&>svg]:size-5",
        family?.tone ?? "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
      )}
    >
      <Icon />
    </span>
  );
}

/** Company monogram (no logos are stored). */
export function CompanyMark({ name }: { name: string | null | undefined }) {
  if (!name) return <span className="text-zinc-400">—</span>;
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden className="flex size-6 shrink-0 items-center justify-center rounded-md bg-navy-900 text-[10px] font-bold text-white dark:bg-navy-700">
        {name.trim()[0]?.toUpperCase()}
      </span>
      <span className="truncate">{name}</span>
    </span>
  );
}
