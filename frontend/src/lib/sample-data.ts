// Illustrative analytics for previewing the charts when the real dataset is too small to show trends.
// Shown only on request (?sample=1) and always labelled "Sample data" in the interface. Never mixed with real data.
import type { Analytics, DateRange } from "./analytics";

function random(seed: number) {
  let state = seed;
  return () => {
    state = (state * 1_103_515_245 + 12_345) % 2_147_483_648;
    return state / 2_147_483_648;
  };
}

export function sampleAnalytics(range: DateRange): Analytics {
  const next = random(42);
  const days = Math.max(1, Math.round((+range.to - +range.from) / 86_400_000));
  const step = days > 31 ? 7 : 1;
  const series = [];
  for (let i = 0; i < Math.ceil(days / step); i++) {
    const date = new Date(+range.from + i * step * 86_400_000);
    const base = step === 1 ? 6 : 38;
    series.push({
      label: date.toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
      value: Math.round(base + base * 0.5 * Math.sin(i / 3) + next() * base * 0.6 + i * (step === 1 ? 0.15 : 1.2)),
    });
  }
  const total = series.reduce((sum, d) => sum + d.value, 0);
  const share = (p: number) => Math.round(total * p);
  return {
    overTime: { series, granularity: step === 1 ? "day" : "week" },
    pipeline: [
      { key: "new", label: "New", value: share(0.31) },
      { key: "screening", label: "Screening", value: share(0.24) },
      { key: "interview", label: "Interview", value: share(0.14) },
      { key: "offer", label: "Offer", value: share(0.04) },
      { key: "hired", label: "Hired", value: share(0.03) },
      { key: "rejected", label: "Rejected", value: share(0.21) },
      { key: "withdrawn", label: "Withdrawn", value: share(0.03) },
    ],
    funnel: [
      { label: "Applied", value: total },
      { label: "Screening", value: share(0.62) },
      { label: "Interview", value: share(0.27) },
      { label: "Offer", value: share(0.08) },
      { label: "Hired", value: share(0.05) },
    ],
    skills: [
      { label: "Python", value: 64 },
      { label: "SQL", value: 58 },
      { label: "Docker", value: 41 },
      { label: "React", value: 36 },
      { label: "AWS", value: 31 },
      { label: "Kubernetes", value: 24 },
      { label: "Power BI", value: 19 },
      { label: "Spark", value: 15 },
    ],
    perJob: [
      { label: "Data Engineer", applications: share(0.34), shortlisted: share(0.07) },
      { label: "Full Stack Developer", applications: share(0.27), shortlisted: share(0.05) },
      { label: "ML Engineer", applications: share(0.21), shortlisted: share(0.04) },
      { label: "DevOps Engineer", applications: share(0.18), shortlisted: share(0.03) },
    ],
    scores: [3, 6, 11, 17, 24, 29, 26, 18, 9, 4].map((value, i) => ({ label: i === 9 ? "90–100" : `${i * 10}–${i * 10 + 9}`, value })),
    totals: { applications: total, candidates: Math.round(total * 0.8) },
  };
}
