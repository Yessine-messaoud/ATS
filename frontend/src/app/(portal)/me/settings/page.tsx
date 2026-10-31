import type { Metadata } from "next";
import { Download } from "lucide-react";

import { PasswordForm, ProfileForm } from "@/components/account-forms";
import { Card, PageHeader, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { currentUser } from "@/lib/session";

import { DeleteAccount, TalentPoolToggle } from "./privacy-controls";

export const metadata: Metadata = { title: "Account & privacy" };

export default async function AccountPage() {
  const [user, profile] = await Promise.all([currentUser(), api.myProfile()]);
  if (!user) return null; // the layout already redirects visitors

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Account & privacy" description="Your sign-in details, who can see your profile, and your data." />
      <Card title="Account">
        <ProfileForm user={user} />
      </Card>
      <Card title="Password" description="Changing it signs you out on every other device.">
        <PasswordForm />
      </Card>
      <Card title="Who can see my profile">
        <TalentPoolToggle consent={profile?.talent_pool_consent ?? null} hasProfile={!!profile} />
      </Card>
      <Card title="My data" description="Everything RecruitAI holds about you: account, profile, CV text and applications.">
        {/* A route handler, not a link to the API: the browser never talks to the backend. */}
        <a href="/me/export" className={buttonClass("secondary")} download>
          <Download className="size-4" aria-hidden /> Download my data (JSON)
        </a>
      </Card>
      <Card title="Delete my account" description="Erases your account, profile, CV and applications. This cannot be undone.">
        <DeleteAccount />
      </Card>
    </div>
  );
}
