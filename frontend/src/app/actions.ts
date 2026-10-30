"use server";

// All mutations go through Server Actions, which call the backend from the server.
import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  ApiError,
  request,
  sendJson,
  type Application,
  type Candidate,
  type CandidateProfile,
  type Conversation,
  type Job,
  type JobProfileInput,
  type Match,
  type Stage,
  type Weights,
} from "@/lib/api";

export type ActionState = { error?: string; ok?: string } | null;

function failure(error: unknown): ActionState {
  return { error: error instanceof ApiError ? error.message : "Something went wrong" };
}

export async function createJob(_: ActionState, formData: FormData): Promise<ActionState> {
  let job: Job;
  try {
    job = await sendJson<Job>("/api/jobs", "POST", { text: String(formData.get("text") ?? "") });
  } catch (error) {
    return failure(error);
  }
  redirect(`/jobs/${job.id}/requirements`);
}

export type UploadResult = { ok: true; id: string; name: string; flags: string[] } | { ok: false; error: string };

export async function uploadCandidate(formData: FormData): Promise<UploadResult> {
  try {
    const candidate = await request<Candidate>("/api/candidates/upload", { method: "POST", body: formData });
    revalidatePath("/candidates");
    return {
      ok: true,
      id: candidate.id,
      name: candidate.profile.identity?.full_name ?? "Unnamed candidate",
      flags: (candidate.extraction.document_flags as string[] | undefined) ?? [],
    };
  } catch (error) {
    return { ok: false, error: error instanceof ApiError ? error.message : "Upload failed" };
  }
}

export async function saveRequirements(jobId: string, profile: JobProfileInput): Promise<ActionState> {
  try {
    await sendJson<Job>(`/api/jobs/${jobId}/requirements`, "PUT", profile);
  } catch (error) {
    return failure(error);
  }
  revalidatePath(`/jobs/${jobId}`, "layout");
  return { ok: "Requirements validated. They are now the reference for matching." };
}

export async function saveWeights(jobId: string, weights: Weights): Promise<ActionState> {
  try {
    await sendJson<Weights>(`/api/jobs/${jobId}/weights`, "PUT", weights);
  } catch (error) {
    return failure(error);
  }
  revalidatePath(`/jobs/${jobId}`, "layout");
  return { ok: "Weights saved." };
}

export async function setJobStatus(jobId: string, status: "open" | "closed"): Promise<void> {
  await sendJson<Job>(`/api/jobs/${jobId}`, "PATCH", { status });
  revalidatePath(`/jobs/${jobId}`, "layout");
}

export async function addToPipeline(jobId: string, candidateId: string): Promise<ActionState> {
  try {
    await sendJson<Application>("/api/applications", "POST", { job_id: jobId, candidate_id: candidateId });
  } catch (error) {
    return failure(error);
  }
  revalidatePath(`/jobs/${jobId}`, "layout");
  return { ok: "Added to the pipeline." };
}

export async function moveApplication(applicationId: string, stage: Stage, reason?: string): Promise<ActionState> {
  try {
    await sendJson<Application>(`/api/applications/${applicationId}`, "PATCH", { stage, reason: reason || null });
  } catch (error) {
    return failure(error);
  }
  refresh();
  return null;
}

export async function scoreMatch(candidateId: string, jobId: string): Promise<void> {
  const match = await sendJson<Match>("/api/matches", "POST", { candidate_id: candidateId, job_id: jobId, explain: true });
  redirect(`/matches/${match.id}`);
}

export async function saveCandidateProfile(candidateId: string, profile: CandidateProfile): Promise<ActionState> {
  let changed: string[];
  try {
    ({ changed_paths: changed } = await sendJson<{ changed_paths: string[] }>(
      `/api/candidates/${candidateId}/profile`,
      "PUT",
      profile,
    ));
  } catch (error) {
    return failure(error);
  }
  revalidatePath(`/candidates/${candidateId}`);
  return { ok: changed.length ? `Saved ${changed.length} change(s).` : "No changes." };
}

export async function mergeCandidates(keepId: string, duplicateId: string): Promise<ActionState> {
  try {
    await sendJson<Candidate>(`/api/candidates/${keepId}/merge`, "POST", { duplicate_id: duplicateId });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/candidates", "layout");
  return { ok: "Merged." };
}

export async function startConversation(formData: FormData): Promise<void> {
  const conversation = await sendJson<Conversation>("/api/agent/conversations", "POST", {
    blind: formData.get("blind") === "on",
  });
  redirect(`/assistant/${conversation.id}`);
}

export type ConversationResult = { conversation?: Conversation; error?: string };

export async function sendAgentMessage(conversationId: string, text: string): Promise<ConversationResult> {
  try {
    const path = `/api/agent/conversations/${conversationId}/messages`;
    return { conversation: await sendJson<Conversation>(path, "POST", { text }) };
  } catch (error) {
    return { error: error instanceof ApiError ? error.message : "The assistant is unavailable" };
  }
}

export async function decideAgentActions(
  conversationId: string,
  decisions: { tool_use_id: string; approved: boolean }[],
): Promise<ConversationResult> {
  try {
    const path = `/api/agent/conversations/${conversationId}/decisions`;
    const conversation = await sendJson<Conversation>(path, "POST", { decisions });
    revalidatePath("/jobs", "layout");
    return { conversation };
  } catch (error) {
    return { error: error instanceof ApiError ? error.message : "The assistant is unavailable" };
  }
}
