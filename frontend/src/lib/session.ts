// Who is signed in, for Server Components, layouts and Server Actions. The token itself never reaches the browser.
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { ApiError, SESSION_COOKIE, request, type Role, type Session, type User } from "./api";

const SECURE = process.env.NODE_ENV === "production";

/** The signed-in user, or null (no cookie, or a session the API no longer accepts). Cached per request. */
export const currentUser = cache(async (): Promise<User | null> => {
  if (!(await cookies()).get(SESSION_COOKIE)) return null;
  try {
    return await request<User>("/api/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
});

/** Where each role lands after signing in. */
export function homeFor(role: Role): string {
  return role === "admin" ? "/admin" : role === "recruiter" ? "/" : "/me";
}

/** The signed-in user with one of `roles`; others are sent to sign in, or to their own home page. */
export async function requireUser(roles: Role[], next?: string): Promise<User> {
  const user = await currentUser();
  if (!user) redirect(next ? `/login?next=${encodeURIComponent(next)}` : "/login");
  if (!roles.includes(user.role)) redirect(homeFor(user.role));
  return user;
}

export async function startSession(session: Session): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, session.token, {
    httpOnly: true,
    secure: SECURE,
    sameSite: "lax",
    path: "/",
    expires: new Date(session.expires_at),
  });
}

export async function endSession(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}

/** Only same-site relative paths, so `?next=` cannot send people to another site after signing in. */
export function safeNext(next: FormDataEntryValue | string | null | undefined): string | null {
  const value = typeof next === "string" ? next : null;
  return value && value.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\") ? value : null;
}
