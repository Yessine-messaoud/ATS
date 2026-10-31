// Display helpers shared by pages.

const ACTIONS: Record<string, string> = {
  "candidate.extracted": "CV extracted",
  "candidate.profile_corrected": "Profile corrected",
  "candidate.merged": "Duplicates merged",
  "candidate.consent_updated": "Consent updated",
  "candidate.exported": "Data exported",
  "candidate.erased": "Candidate erased",
  "job.extracted": "Job created",
  "job.requirements_validated": "Requirements validated",
  "job.weights_updated": "Weights updated",
  "job.status_changed": "Job status changed",
  "application.created": "Added to pipeline",
  "application.stage_changed": "Stage changed",
  "match.scored": "Match scored",
  "document.purged": "Document purged",
};

export function actionLabel(action: string): string {
  return ACTIONS[action] ?? action.replace(/[._]/g, " ");
}

const RELATIVE = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function timeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return RELATIVE.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function initials(name: string | null | undefined): string {
  const parts = (name ?? "?").trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "?") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}
