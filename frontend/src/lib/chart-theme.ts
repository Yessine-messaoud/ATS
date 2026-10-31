// Chart colours. A plain module (not "use client") so server components can pass them to the chart widgets.
export const CHART_COLORS = {
  brand: "#3d64f5",
  brandSoft: "#98b4ff",
  lavender: "#8b5cf6",
  grid: "rgba(113,113,122,0.15)",
  axis: "#71717a",
};

export const STAGE_CHART_COLORS: Record<string, string> = {
  new: "#94a3b8",
  screening: "#38bdf8",
  interview: "#3d64f5",
  offer: "#8b5cf6",
  hired: "#10b981",
  rejected: "#f87171",
  withdrawn: "#d4d4d8",
};
