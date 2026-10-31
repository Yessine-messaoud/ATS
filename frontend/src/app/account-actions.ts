"use server";

// The signed-in user's own account, and (recruiters) their company and team. Shared by staff and candidates.
import { revalidatePath } from "next/cache";

import { ApiError, sendJson, type CreatedUser, type Organization, type Session, type User } from "@/lib/api";
import { startSession } from "@/lib/session";

export type FormState = { error?: string; ok?: string; secret?: string; at?: number } | null;

function failure(error: unknown): FormState {
  const message = error instanceof ApiError ? error.message : "Something went wrong";
  return { error: message.replace(/^./, (c) => c.toUpperCase()) };
}

function text(formData: FormData, name: string): string | null {
  const value = String(formData.get(name) ?? "").trim();
  return value || null;
}

export async function updateProfile(_: FormState, formData: FormData): Promise<FormState> {
  try {
    await sendJson<User>("/api/auth/me", "PATCH", {
      full_name: text(formData, "full_name") ?? "",
      job_title: text(formData, "job_title"),
      phone: text(formData, "phone"),
      locale: formData.get("locale") === "fr" ? "fr" : "en",
      preferences: {
        email_digest: formData.get("email_digest") === "on",
        notify_new_applications: formData.get("notify_new_applications") === "on",
      },
    });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/", "layout");
  return { ok: "Profile saved.", at: Date.now() };
}

export async function changePassword(_: FormState, formData: FormData): Promise<FormState> {
  if (formData.get("new_password") !== formData.get("confirm")) return { error: "The two new passwords differ." };
  try {
    const session = await sendJson<Session>("/api/auth/password", "POST", {
      current_password: String(formData.get("current_password") ?? ""),
      new_password: String(formData.get("new_password") ?? ""),
    });
    await startSession(session); // every other session was signed out; keep this one
  } catch (error) {
    return failure(error);
  }
  return { ok: "Password changed. Your other devices were signed out.", at: Date.now() };
}

export async function updateOrganization(_: FormState, formData: FormData): Promise<FormState> {
  try {
    await sendJson<Organization>("/api/organization", "PUT", {
      name: text(formData, "name") ?? "",
      website: text(formData, "website"),
      industry: text(formData, "industry"),
      size: text(formData, "size"),
      city: text(formData, "city"),
      description: text(formData, "description"),
    });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/", "layout");
  return { ok: "Company profile saved.", at: Date.now() };
}

export async function addMember(_: FormState, formData: FormData): Promise<FormState> {
  let created: CreatedUser;
  try {
    created = await sendJson<CreatedUser>("/api/organization/members", "POST", {
      email: text(formData, "email") ?? "",
      full_name: text(formData, "full_name") ?? "",
      job_title: text(formData, "job_title"),
    });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/company");
  return { ok: `${created.user.full_name} can now sign in with ${created.user.email}.`, secret: created.temporary_password, at: Date.now() };
}

export async function setMemberActive(memberId: string, active: boolean): Promise<FormState> {
  try {
    await sendJson<User>(`/api/organization/members/${memberId}`, "PATCH", { is_active: active });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/company");
  return { ok: active ? "Account reactivated." : "Account deactivated and signed out." };
}
