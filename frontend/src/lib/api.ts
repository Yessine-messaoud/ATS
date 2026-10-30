// Server-side client for the FastAPI backend. Only imported by Server Components and Server Actions:
// the browser never talks to the backend directly (no CORS, no public API URL).
import { connection } from "next/server";

import type { components } from "./api-types";

export type Schemas = components["schemas"];
export type Job = Schemas["JobOut"];
export type Candidate = Schemas["CandidateOut"];
export type CandidateProfile = Schemas["CandidateProfile"];
export type JobProfile = Schemas["JobProfile-Output"];
export type JobProfileInput = Schemas["JobProfile-Input"];
export type Ranking = Schemas["RankingOut"];
export type RankedCandidate = Schemas["RankedCandidateOut"];
export type Application = Schemas["ApplicationOut"];
export type Match = Schemas["MatchOut"];
export type MatchResult = Schemas["MatchResult"];
export type Factor = Schemas["Factor"];
export type Weights = Schemas["ScoringWeights"];
export type CandidateDocument = Schemas["CandidateDocumentOut"];
export type Recommendation = Schemas["RecommendedJobOut"];
export type Stage = Schemas["ApplicationOut"]["stage"];
export type Duplicate = Schemas["DuplicateOut"];
export type Conversation = Schemas["ConversationOut"];
export type AuditEntry = Schemas["AuditEntryOut"];
export type Erasure = Schemas["ErasureOut"];

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`)
      .join("; ");
  }
  if (detail && typeof detail === "object" && "message" in detail) return String(detail.message);
  return "unexpected error";
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, cache: "no-store" });
  } catch {
    throw new ApiError(503, `the API is unreachable at ${API_URL}`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, describe(body.detail));
  }
  return (await response.json()) as T;
}

export function sendJson<T>(path: string, method: "POST" | "PUT" | "PATCH", body: unknown): Promise<T> {
  return request<T>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

/** Reads used by pages; they always run at request time (live data, and nothing is fetched during `next build`). */
async function read<T>(path: string): Promise<T> {
  await connection();
  return request<T>(path);
}

export const api = {
  jobs: () => read<Job[]>("/api/jobs"),
  job: (id: string) => read<Job>(`/api/jobs/${id}`),
  ranking: (id: string, blind: boolean) => read<Ranking>(`/api/jobs/${id}/ranking?blind=${blind}&limit=100`),
  applications: (id: string, blind: boolean) => read<Application[]>(`/api/jobs/${id}/applications?blind=${blind}`),
  candidates: () => read<Candidate[]>("/api/candidates?limit=200"),
  candidate: (id: string) => read<Candidate>(`/api/candidates/${id}`),
  document: (id: string) => read<CandidateDocument>(`/api/candidates/${id}/document`),
  recommendations: (id: string) => read<Recommendation[]>(`/api/candidates/${id}/recommendations`),
  match: (id: string) => read<Match>(`/api/matches/${id}`),
  duplicates: (id: string) => read<Duplicate[]>(`/api/candidates/${id}/duplicates`),
  conversation: (id: string) => read<Conversation>(`/api/agent/conversations/${id}`),
  audit: (filters: Record<string, string | undefined>) => {
    const query = new URLSearchParams(Object.entries(filters).filter((e): e is [string, string] => !!e[1]));
    return read<AuditEntry[]>(`/api/audit?${query}`);
  },
};
