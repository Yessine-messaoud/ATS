import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Notice } from "@/components/ui";
import { currentUser, homeFor, safeNext } from "@/lib/session";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const params = await searchParams;
  const next = safeNext(typeof params.next === "string" ? params.next : null);
  const user = await currentUser();
  if (user) redirect(next ?? homeFor(user.role));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
        <p className="mt-1 text-sm text-zinc-500">Sign in to your recruiter, candidate or admin account.</p>
      </div>
      {params.expired && <Notice tone="blue">Your session has ended. Please sign in again.</Notice>}
      <LoginForm next={next} />
      <p className="text-center text-sm text-zinc-500">
        New here?{" "}
        <Link href={next ? `/signup?next=${encodeURIComponent(next)}` : "/signup"} className="font-medium text-brand-700 hover:underline dark:text-brand-300">
          Create an account
        </Link>
      </p>
    </div>
  );
}
