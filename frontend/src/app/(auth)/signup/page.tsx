import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser, homeFor, safeNext } from "@/lib/session";

import { SignupForm } from "./signup-form";

export const metadata: Metadata = { title: "Create an account" };

export default async function SignupPage({ searchParams }: PageProps<"/signup">) {
  const params = await searchParams;
  const user = await currentUser();
  if (user) redirect(homeFor(user.role));
  const next = safeNext(typeof params.next === "string" ? params.next : null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
        <p className="mt-1 text-sm text-zinc-500">Apply to jobs as a candidate, or hire as a company.</p>
      </div>
      <SignupForm initialType={params.type === "company" ? "company" : "candidate"} next={next} />
      <p className="text-center text-sm text-zinc-500">
        Already have an account?{" "}
        <Link href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"} className="font-medium text-brand-700 hover:underline dark:text-brand-300">
          Sign in
        </Link>
      </p>
    </div>
  );
}
