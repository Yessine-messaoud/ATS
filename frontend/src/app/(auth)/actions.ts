"use server";

import { redirect } from "next/navigation";

import { ApiError, request, sendJson, type Session } from "@/lib/api";
import { endSession, homeFor, safeNext, startSession } from "@/lib/session";

export type AuthState = { error?: string; email?: string } | null;

function message(error: unknown): string {
  return error instanceof ApiError ? error.message.replace(/^./, (c) => c.toUpperCase()) : "Something went wrong";
}

export async function signIn(_: AuthState, formData: FormData): Promise<AuthState> {
  const email = String(formData.get("email") ?? "");
  let session: Session;
  try {
    session = await sendJson<Session>("/api/auth/login", "POST", { email, password: String(formData.get("password") ?? "") });
  } catch (error) {
    return { error: message(error), email };
  }
  await startSession(session);
  redirect(safeNext(formData.get("next")) ?? homeFor(session.user.role));
}

export async function signUp(_: AuthState, formData: FormData): Promise<AuthState> {
  const email = String(formData.get("email") ?? "");
  const accountType = formData.get("account_type") === "company" ? "company" : "candidate";
  if (formData.get("password") !== formData.get("confirm")) return { error: "The two passwords differ.", email };
  if (formData.get("terms") !== "on") return { error: "Please accept the privacy notice to continue.", email };
  let session: Session;
  try {
    session = await sendJson<Session>("/api/auth/register", "POST", {
      account_type: accountType,
      email,
      password: String(formData.get("password") ?? ""),
      full_name: String(formData.get("full_name") ?? ""),
      company_name: accountType === "company" ? String(formData.get("company_name") ?? "") : null,
      job_title: String(formData.get("job_title") ?? "") || null,
    });
  } catch (error) {
    return { error: message(error), email };
  }
  await startSession(session);
  redirect(safeNext(formData.get("next")) ?? homeFor(session.user.role));
}

export async function signOut(): Promise<void> {
  try {
    await request<void>("/api/auth/logout", { method: "POST" });
  } catch {
    // Already expired: nothing to revoke.
  }
  await endSession();
  redirect("/login");
}
