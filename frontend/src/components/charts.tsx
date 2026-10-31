"use client";

// Chart widgets (Recharts). They receive pre-aggregated, non-personal series from server components.
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FlaskConical } from "lucide-react";

import { CHART_COLORS, STAGE_CHART_COLORS } from "@/lib/chart-theme";

import { cx } from "./ui";

function ChartTooltip({ active, payload, label, unit }: { active?: boolean; payload?: { name?: string; value?: number; color?: string; payload?: { fill?: string } }[]; label?: string | number; unit?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
      {label !== undefined && <p className="mb-1 font-medium text-zinc-900 dark:text-zinc-100">{label}</p>}
      {payload.map((entry, index) => (
        <p key={index} className="flex items-center gap-1.5 text-zinc-600 dark:text-zinc-300">
          <span className="size-2 rounded-full" style={{ background: entry.color ?? entry.payload?.fill }} />
          {entry.name}: <span className="font-semibold tabular-nums">{entry.value}</span>
          {unit}
        </p>
      ))}
    </div>
  );
}

export function SampleBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
      <FlaskConical className="size-3" aria-hidden /> Sample data
    </span>
  );
}

export function ChartCard({
  title,
  description,
  sample,
  actions,
  children,
  className,
}: {
  title: string;
  description?: string;
  sample?: boolean;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cx(
        "flex flex-col rounded-xl border border-zinc-200/80 bg-white p-5 shadow-[0_1px_2px_rgba(16,24,64,0.04),0_1px_3px_rgba(16,24,64,0.06)] dark:border-zinc-800 dark:bg-zinc-900",
        className,
      )}
    >
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
            {title}
            {sample && <SampleBadge />}
          </h2>
          {description && <p className="mt-0.5 text-xs text-zinc-500">{description}</p>}
        </div>
        {actions}
      </header>
      <div className="flex-1">{children}</div>
    </section>
  );
}

function NoData({ children = "No data in this period." }: { children?: ReactNode }) {
  return <div className="flex h-full min-h-40 items-center justify-center text-sm text-zinc-500">{children}</div>;
}

export function TrendChart({ data, height = 220, name = "Applications" }: { data: { label: string; value: number }[]; height?: number; name?: string }) {
  if (data.every((d) => d.value === 0)) return <NoData />;
  return (
    <div style={{ height }} role="img" aria-label={`${name} over time`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.brand} stopOpacity={0.28} />
              <stop offset="100%" stopColor={CHART_COLORS.brand} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.axis }} minTickGap={16} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.axis }} />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: CHART_COLORS.brandSoft }} />
          <Area type="monotone" dataKey="value" name={name} stroke={CHART_COLORS.brand} strokeWidth={2} fill="url(#trendFill)" activeDot={{ r: 4 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DonutChart({ data, centerLabel }: { data: { key: string; label: string; value: number }[]; centerLabel: string }) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (total === 0) return <NoData />;
  const shown = data.filter((d) => d.value > 0);
  return (
    <div className="flex flex-col items-center gap-5">
      <div className="relative size-40 shrink-0" role="img" aria-label="Candidate pipeline by stage">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={shown} dataKey="value" nameKey="label" innerRadius="64%" outerRadius="100%" paddingAngle={2} stroke="none">
              {shown.map((d) => (
                <Cell key={d.key} fill={STAGE_CHART_COLORS[d.key] ?? CHART_COLORS.brand} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums">{total}</span>
          <span className="text-[11px] text-zinc-500">{centerLabel}</span>
        </div>
      </div>
      <ul className="grid w-full grid-cols-2 gap-x-5 gap-y-1.5 text-sm">
        {data.map((d) => (
          <li key={d.key} className={cx("flex items-center justify-between gap-2", d.value === 0 && "opacity-50")}>
            <span className="flex min-w-0 items-center gap-2">
              <span className="size-2.5 shrink-0 rounded-sm" style={{ background: STAGE_CHART_COLORS[d.key] ?? CHART_COLORS.brand }} />
              <span className="truncate">{d.label}</span>
            </span>
            <span className="whitespace-nowrap tabular-nums text-zinc-500">
              {d.value} · {Math.round((d.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Recruitment funnel: each step's width is its share of the first step, with step-to-step conversion. */
export function Funnel({ steps }: { steps: { label: string; value: number }[] }) {
  const first = steps[0]?.value ?? 0;
  if (first === 0) return <NoData />;
  return (
    <ol className="space-y-2" aria-label="Recruitment funnel">
      {steps.map((step, index) => {
        const width = Math.max(10, (step.value / first) * 100);
        const previous = index > 0 ? steps[index - 1].value : null;
        const conversion = previous ? Math.round((step.value / previous) * 100) : null;
        return (
          <li key={step.label} className="grid grid-cols-[6.5rem_1fr_3.5rem] items-center gap-3 text-sm">
            <span className="truncate text-zinc-600 dark:text-zinc-300">{step.label}</span>
            <div className="flex justify-center">
              <div
                className={cx(
                  "flex h-8 items-center justify-center rounded-md text-xs font-semibold transition-all",
                  step.value === 0 ? "bg-zinc-100 text-zinc-400 dark:bg-zinc-800" : "text-white",
                )}
                style={{
                  width: `${width}%`,
                  background: step.value === 0 ? undefined : `color-mix(in srgb, ${CHART_COLORS.brand} ${100 - index * 14}%, ${CHART_COLORS.lavender})`,
                }}
                title={`${step.label}: ${step.value}`}
              >
                {step.value}
              </div>
            </div>
            <span className="text-right text-xs tabular-nums text-zinc-500">{conversion === null ? "" : `${conversion}%`}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function PercentBars({ data, height = 240, name = "Candidates" }: { data: { label: string; value: number }[]; height?: number; name?: string }) {
  if (data.length === 0) return <NoData />;
  return (
    <div style={{ height }} role="img" aria-label={`${name} by skill`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} interval={0} tick={{ fontSize: 10, fill: CHART_COLORS.axis }} />
          <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.axis }} unit="%" />
          <Tooltip content={<ChartTooltip unit="%" />} cursor={{ fill: "rgba(61,100,245,0.06)" }} />
          <Bar dataKey="value" name={name} radius={[6, 6, 0, 0]} maxBarSize={36} fill={CHART_COLORS.brand}>
            <LabelList dataKey="value" position="top" formatter={(v: unknown) => `${v}%`} style={{ fontSize: 10, fill: CHART_COLORS.axis }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComparisonBars({
  data,
  series,
}: {
  data: Record<string, string | number>[];
  series: { key: string; name: string; color: string }[];
}) {
  if (data.length === 0) return <NoData />;
  const height = Math.max(160, data.length * 44 + 40);
  return (
    <div style={{ height }} role="img" aria-label="Applications per job">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }} barGap={2}>
          <CartesianGrid horizontal={false} stroke={CHART_COLORS.grid} />
          <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.axis }} />
          <YAxis type="category" dataKey="label" width={130} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.axis }} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(61,100,245,0.06)" }} />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[0, 4, 4, 0]} maxBarSize={14} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex justify-end gap-4 text-xs text-zinc-500">
        {series.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

export function Histogram({ data, height = 220 }: { data: { label: string; value: number }[]; height?: number }) {
  if (data.every((d) => d.value === 0)) return <NoData />;
  return (
    <div style={{ height }} role="img" aria-label="Distribution of match scores">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, left: -20, bottom: 0 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={CHART_COLORS.grid} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: CHART_COLORS.axis }} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.axis }} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(61,100,245,0.06)" }} />
          <Bar dataKey="value" name="Candidates" radius={[4, 4, 0, 0]}>
            {data.map((d, index) => (
              <Cell key={d.label} fill={index >= 7 ? "#10b981" : index >= 5 ? "#f59e0b" : CHART_COLORS.brandSoft} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
