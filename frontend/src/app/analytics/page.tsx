import type { Metadata } from "next";
import Link from "next/link";
import { FlaskConical, Info } from "lucide-react";

import { ChartCard, ComparisonBars, DonutChart, Funnel, Histogram, PercentBars, TrendChart } from "@/components/charts";
import { Notice, PageHeader, Stat } from "@/components/ui";
import { analytics, parseRange } from "@/lib/analytics";
import { CHART_COLORS } from "@/lib/chart-theme";
import { api, loadWorkspace } from "@/lib/api";
import { sampleAnalytics } from "@/lib/sample-data";

import { RangeFilter } from "./range-filter";

export const metadata: Metadata = { title: "Analytics" };

const isoDay = (date: Date) => date.toISOString().slice(0, 10);

export default async function AnalyticsPage(props: PageProps<"/analytics">) {
  const params = await props.searchParams;
  const range = parseRange(params);
  const sample = params.sample === "1";
  const [workspace, stageChanges] = await Promise.all([
    loadWorkspace({ rankings: true }),
    api.audit({ action: "application.stage_changed", limit: "500" }),
  ]);
  const data = sample ? sampleAnalytics(range) : analytics(workspace, stageChanges, range);
  const sparse = !sample && data.totals.applications < 10;
  const sampleHref = (on: boolean) => {
    const next = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => typeof e[1] === "string"));
    if (on) next.set("sample", "1");
    else next.delete("sample");
    return `/analytics?${next}`;
  };
  const conversion = data.funnel[0]?.value ? Math.round(((data.funnel.at(-1)?.value ?? 0) / data.funnel[0].value) * 100) : 0;
  const interviewRate = data.funnel[0]?.value ? Math.round(((data.funnel[2]?.value ?? 0) / data.funnel[0].value) * 100) : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description={`${range.from.toLocaleDateString("en-GB")} – ${range.to.toLocaleDateString("en-GB")}`}
        actions={<RangeFilter current={params.range === "custom" ? "custom" : range.key} from={isoDay(range.from)} to={isoDay(range.to)} />}
      />

      {sample ? (
        <Notice tone="amber" icon={<FlaskConical />}>
          <strong>Sample data.</strong> These charts show illustrative figures to preview the analytics, not your recruitment
          data. <Link href={sampleHref(false)} className="font-medium underline">Back to real data</Link>
        </Notice>
      ) : (
        sparse && (
          <Notice tone="blue" icon={<Info />}>
            Only {data.totals.applications} application{data.totals.applications === 1 ? "" : "s"} in this period: trends become
            meaningful with more activity.{" "}
            <Link href={sampleHref(true)} className="font-medium underline">
              Preview with sample data
            </Link>
          </Notice>
        )
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Applications" value={data.totals.applications} hint="in the period" />
        <Stat label="New candidates" value={data.totals.candidates} hint="added in the period" />
        <Stat label="Interview rate" value={`${interviewRate}%`} hint="reached the interview stage" />
        <Stat label="Hire rate" value={`${conversion}%`} hint="of applications hired" />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard
          title="Applications over time"
          description={`New applications per ${data.overTime.granularity}`}
          sample={sample}
          className="xl:col-span-2"
        >
          <TrendChart data={data.overTime.series} height={240} />
        </ChartCard>
        <ChartCard title="Candidate pipeline" description="Applications by current stage" sample={sample}>
          <DonutChart data={data.pipeline} centerLabel="applications" />
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard title="Recruitment funnel" description="Furthest stage reached; % = conversion from the previous step" sample={sample}>
          <Funnel steps={data.funnel} />
        </ChartCard>
        <ChartCard title="Top candidate skills" description="Share of candidates listing each skill" sample={sample} className="xl:col-span-2">
          <PercentBars data={data.skills} height={250} />
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Applications per job" description="All applications and those shortlisted (interview or later)" sample={sample}>
          <ComparisonBars
            data={data.perJob}
            series={[
              { key: "applications", name: "Applications", color: CHART_COLORS.brand },
              { key: "shortlisted", name: "Shortlisted", color: CHART_COLORS.lavender },
            ]}
          />
        </ChartCard>
        <ChartCard
          title="Candidate match scores"
          description="Each candidate's best score across open jobs (deterministic engine, not AI)"
          sample={sample}
        >
          <Histogram data={data.scores} />
        </ChartCard>
      </div>
    </div>
  );
}
