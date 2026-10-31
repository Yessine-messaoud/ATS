"use server";

import { revalidatePath } from "next/cache";

import type { FormState } from "@/app/account-actions";
import { ApiError, request, sendJson, type CreatedUser, type OrganizationAdmin, type User } from "@/lib/api";

function failure(error: unknown): FormState {
  const message = error instanceof ApiError ? error.message : "Something went wrong";
  return { error: message.replace(/^./, (c) => c.toUpperCase()) };
}

const STATUS_DONE = { active: "approved", suspended: "suspended", pending: "set back to pending" } as const;

export async function setCompanyStatus(id: string, status: keyof typeof STATUS_DONE): Promise<FormState> {
  let organization: OrganizationAdmin;
  try {
    organization = await sendJson<OrganizationAdmin>(`/api/admin/organizations/${id}`, "PATCH", { status });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/admin", "layout");
  return { ok: `${organization.name} ${STATUS_DONE[status]}.` };
}

export async function createStaffUser(_: FormState, formData: FormData): Promise<FormState> {
  const role = formData.get("role") === "admin" ? "admin" : "recruiter";
  let created: CreatedUser;
  try {
    created = await sendJson<CreatedUser>("/api/admin/users", "POST", {
      email: String(formData.get("email") ?? "").trim(),
      full_name: String(formData.get("full_name") ?? "").trim(),
      role,
      organization_id: role === "recruiter" ? String(formData.get("organization_id") ?? "") || null : null,
      job_title: String(formData.get("job_title") ?? "").trim() || null,
    });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/admin", "layout");
  return { ok: `${created.user.full_name} can now sign in with ${created.user.email}.`, secret: created.temporary_password, at: Date.now() };
}

export async function setUserActive(id: string, active: boolean): Promise<FormState> {
  try {
    await sendJson<User>(`/api/admin/users/${id}`, "PATCH", { is_active: active });
  } catch (error) {
    return failure(error);
  }
  revalidatePath("/admin", "layout");
  return { ok: active ? "Account reactivated." : "Account deactivated and signed out everywhere." };
}

export async function resetUserPassword(id: string): Promise<FormState> {
  try {
    const created = await request<CreatedUser>(`/api/admin/users/${id}/reset-password`, { method: "POST" });
    return { ok: `New temporary password for ${created.user.email}.`, secret: created.temporary_password, at: Date.now() };
  } catch (error) {
    return failure(error);
  }
}
