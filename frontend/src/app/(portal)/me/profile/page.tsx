import type { Metadata } from "next";
import Link from "next/link";
import { FileUp, Info } from "lucide-react";

import { Card, Empty, Notice, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

import { AutoRefresh } from "../application-actions";
import { MyProfileEditor, ReplaceCv } from "./profile-editor";

export const metadata: Metadata = { title: "My profile" };

export default async function MyProfilePage() {
  const [profile, tasks] = await Promise.all([api.myProfile(), api.myTasks()]);
  const reading = tasks.some((t) => t.status === "queued" || t.status === "processing");

  if (!profile) {
    return (
      <div className="space-y-6">
        {reading && <AutoRefresh />}
        <PageHeader title="My profile" />
        <Card>
          <Empty icon={<FileUp />} title={reading ? "We are reading your CV…" : "No CV yet"}>
            {reading ? (
              "Your profile appears here in a minute or two."
            ) : (
              <>
                Your profile is built from your CV when you{" "}
                <Link href="/careers" className="font-medium text-brand-700 hover:underline dark:text-brand-300">
                  apply to a job
                </Link>
                .
              </>
            )}
          </Empty>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {reading && <AutoRefresh />}
      <PageHeader
        title="My profile"
        description={`Read from ${profile.filename ?? "your CV"} · updated ${formatDate(profile.updated_at)}. Companies you apply to see this profile.`}
      />
      {reading && <Notice tone="blue">We are reading your new CV. This profile will be replaced in a minute or two.</Notice>}
      <Notice tone="blue" icon={<Info />}>
        Check what was read and correct or remove anything wrong. Items you add or change are marked <em>declared by you</em>: recruiters see them, but they
        only count in matching once they appear in your CV, so the easiest way to add experience is to send an updated CV.
      </Notice>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <MyProfileEditor initial={profile.profile} />
        <div className="space-y-6">
          <Card title="Update my CV" description="Replaces this profile. Your applications are kept.">
            <ReplaceCv />
          </Card>
          {profile.flags.length > 0 && (
            <Notice tone="amber">Something in your document could not be read normally (hidden or unusual text). Sending a simpler PDF usually helps.</Notice>
          )}
        </div>
      </div>
    </div>
  );
}
