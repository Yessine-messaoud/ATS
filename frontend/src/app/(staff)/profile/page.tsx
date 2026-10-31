import type { Metadata } from "next";
import { Building2, CalendarClock, ShieldCheck } from "lucide-react";

import { PasswordForm, ProfileForm } from "@/components/account-forms";
import { Badge, Card, PageHeader } from "@/components/ui";
import { formatDate, initials } from "@/lib/format";
import { requireUser } from "@/lib/session";

export const metadata: Metadata = { title: "My profile" };

const ROLE_LABEL = { admin: "Platform administrator", recruiter: "Recruiter", candidate: "Candidate" } as const;

export default async function ProfilePage() {
  const user = await requireUser(["recruiter", "admin"], "/profile");
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title="My profile" description="How you appear to your team and in the activity log." />

      <section className="flex flex-wrap items-center gap-4 rounded-xl border border-zinc-200/80 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
        <span className="flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-lavender-600 text-lg font-semibold text-white">
          {initials(user.full_name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-lg font-semibold">{user.full_name}</p>
          <p className="text-sm text-zinc-500">{[user.job_title, user.email].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge tone="indigo">
            <ShieldCheck className="size-3" aria-hidden /> {ROLE_LABEL[user.role]}
          </Badge>
          {user.organization && (
            <Badge>
              <Building2 className="size-3" aria-hidden /> {user.organization.name}
            </Badge>
          )}
          {user.last_login_at && (
            <Badge>
              <CalendarClock className="size-3" aria-hidden /> Last sign-in {formatDate(user.last_login_at)}
            </Badge>
          )}
        </div>
      </section>

      <Card title="Personal details">
        <ProfileForm user={user} />
      </Card>
      <Card title="Password" description="Changing it signs you out on every other device.">
        <PasswordForm />
      </Card>
    </div>
  );
}
