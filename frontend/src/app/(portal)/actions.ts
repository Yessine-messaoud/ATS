"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { FormState } from "@/app/account-actions";
import { ApiError, request, sendJson, type ApplyResult, type CandidateProfile, type CvTask, type PortalApplication, type PortalProfile } from "@/lib/api";
import { endSession } from "@/lib/session";

function failure(error: unknown): FormState {
  const message = error instanceof ApiError ? error.message : "Something went wrong";
  return { error: message.replace(/^./, (c) => c.toUpperCase()) };
}

export async function applyToJob(_: FormState, formData: FormData): Promise<FormState> {
  const file = formData.get("file");
  const body = new FormData();
  body.set("job_id", String(formData.get("job_id") ?? ""));
  if (file instanceof File && file.size > 0) body.set("file", file);
  if (formData.get("talent_pool_consent") !== null) body.set("talent_pool_consent", formData.get("talent_pool_consent") === "on" ? "true" : "false");
  let result: ApplyResult;
  try {
    result = await request<ApplyResult>("/api/portal/applications", { method: "POST", body });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/me");
  redirect(result.task ? "/me?applied=processing" : "/me?applied=done");
}

export async function withdrawApplication(id: string): Promise<FormState> {
  try {
    await request<PortalApplication>(`/api/portal/applications/${id}/withdraw`, { method: "POST" });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/me");
  return { ok: "Application withdrawn. The company has been informed." };
}

export async function saveMyProfile(profile: CandidateProfile): Promise<FormState> {
  try {
    await sendJson<PortalProfile>("/api/portal/profile", "PUT", profile);
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/me/profile");
  return { ok: "Profile saved." };
}

export async function replaceCv(_: FormState, formData: FormData): Promise<FormState> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "Choose a file first." };
  const body = new FormData();
  body.set("file", file);
  try {
    await request<CvTask>("/api/portal/cv", { method: "POST", body });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/me", "layout");
  return { ok: "Thanks! We are reading your new CV; your profile updates in about a minute.", at: Date.now() };
}

export async function setTalentPool(consent: boolean): Promise<FormState> {
  try {
    await sendJson<PortalProfile>("/api/portal/consent", "PUT", { consent });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/me", "layout");
  return { ok: consent ? "Companies on RecruitAI can now find your profile." : "Only companies you apply to can see your profile." };
}

export async function deleteAccount(_: FormState, formData: FormData): Promise<FormState> {
  if (formData.get("confirm") !== "DELETE") return { error: "Type DELETE to confirm." };
  try {
    await request<void>("/api/portal/account", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: String(formData.get("password") ?? "") }),
    });
  } catch (error) {
    return failure(error);
  }
  await endSession();
  redirect("/careers?deleted=1");
}
