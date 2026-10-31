// Server-side client for the FastAPI backend. Only imported by Server Components and Server Actions:
// the browser never talks to the backend directly (no CORS, no public API URL). The session token lives in an
// httpOnly cookie that only this server reads, and is forwarded as a bearer token.
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
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
export type User = Schemas["UserOut"];
export type Role = User["role"];
export type Organization = Schemas["OrganizationOut"];
export type OrganizationAdmin = Schemas["OrganizationAdminOut"];
export type CreatedUser = Schemas["CreatedUserOut"];
export type Session = Schemas["SessionOut"];
export type AdminOverview = Schemas["OverviewOut"];
export type AdminTask = Schemas["AdminTaskOut"];
export type PublicJob = Schemas["PublicJobOut"];
export type PublicJobDetail = Schemas["PublicJobDetailOut"];
export type PortalApplication = Schemas["PortalApplicationOut"];
export type PortalProfile = Schemas["PortalProfileOut"];
export type CvTask = Schemas["CvTaskOut"];
export type ApplyResult = Schemas["ApplyOut"];

export const SESSION_COOKIE = "ra_session";

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

/** The signed-in user's bearer header, when there is a session cookie (none outside a request). */
export async function authHeaders(): Promise<Record<string, string>> {
  try {
    const token = (await cookies()).get(SESSION_COOKIE)?.value;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const headers = { ...(await authHeaders()), ...(init?.headers as Record<string, string> | undefined) };
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(503, `the API is unreachable at ${API_URL}`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, describe(body.detail));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function sendJson<T>(path: string, method: "POST" | "PUT" | "PATCH", body: unknown): Promise<T> {
  return request<T>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

/** Reads used by pages; they always run at request time (live data, and nothing is fetched during `next build`). */
async function read<T>(path: string): Promise<T> {
  await connection();
  try {
    return await request<T>(path);
  } catch (error) {
    // The session expired or was revoked (password change, deactivation): sign in again.
    if (error instanceof ApiError && error.status === 401) redirect("/login?expired=1");
    throw error;
  }
}

/** Reads that may legitimately be missing (404 → null), e.g. a candidate without a profile yet. */
async function readOptional<T>(path: string): Promise<T | null> {
  try {
    return await read<T>(path);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

function query(filters: Record<string, string | undefined>): string {
  return new URLSearchParams(Object.entries(filters).filter((e): e is [string, string] => !!e[1])).toString();
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
  audit: (filters: Record<string, string | undefined>) => read<AuditEntry[]>(`/api/audit?${query(filters)}`),
  // Accounts and company
  organization: () => read<Organization>("/api/organization"),
  members: () => read<User[]>("/api/organization/members"),
  // Platform administration
  adminOverview: () => read<AdminOverview>("/api/admin/overview"),
  adminOrganizations: (status?: string) => read<OrganizationAdmin[]>(`/api/admin/organizations?${query({ status })}`),
  adminUsers: (filters: Record<string, string | undefined>) => read<User[]>(`/api/admin/users?${query(filters)}`),
  adminTasks: () => read<AdminTask[]>("/api/admin/tasks"),
  // Careers page (public) and candidate portal
  publicJobs: (filters: Record<string, string | undefined>) => read<PublicJob[]>(`/api/public/jobs?${query(filters)}`),
  publicJob: (id: string) => readOptional<PublicJobDetail>(`/api/public/jobs/${id}`),
  myApplications: () => read<PortalApplication[]>("/api/portal/applications"),
  myTasks: () => read<CvTask[]>("/api/portal/tasks"),
  myProfile: () => readOptional<PortalProfile>("/api/portal/profile"),
};

/** Jobs, candidates and every job's applications (and, on demand, the open jobs' rankings) for dashboards. */
export async function loadWorkspace({ rankings = false }: { rankings?: boolean } = {}) {
  const [jobs, candidates] = await Promise.all([api.jobs(), api.candidates()]);
  const [applications, rankingList] = await Promise.all([
    Promise.all(jobs.map((job) => api.applications(job.id, false))).then((lists) => lists.flat()),
    rankings ? Promise.all(jobs.filter((job) => job.status === "open").map((job) => api.ranking(job.id, false))) : [],
  ]);
  return { jobs, candidates, applications, rankings: rankingList };
}
