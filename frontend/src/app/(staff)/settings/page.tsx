import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import type { ReactNode } from "react";
import { Bot, Clock, Cpu, Lock, Palette, ShieldCheck, Users } from "lucide-react";

import { ThemeSegmented } from "@/components/theme";
import { Badge, Card, PageHeader } from "@/components/ui";
import { request } from "@/lib/api";
import type { components } from "@/lib/api-types";

export const metadata: Metadata = { title: "Settings" };

type Policy = components["schemas"]["PrivacyPolicyOut"];

function Row({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3">
      <span className="flex items-center gap-2.5 text-sm font-medium">
        <span className="text-zinc-400 [&>svg]:size-4">{icon}</span>
        {label}
      </span>
      <span className="text-sm text-zinc-600 dark:text-zinc-300">{children}</span>
    </div>
  );
}

/** Preferences and the current configuration (read-only: it is set on the server through environment variables). */
export default async function SettingsPage() {
  await connection();
  const policy = await request<Policy>("/api/privacy/policy");

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Settings" description="Display preferences, and how this installation is configured." />

      <Card title="Appearance" description="Stored in this browser only.">
        <Row icon={<Palette />} label="Theme">
          <ThemeSegmented />
        </Row>
      </Card>

      <Card title="AI & scoring" description="Set by the server administrator (environment variables); shown here for transparency.">
        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
          <Row icon={<Bot />} label="AI provider">
            {policy.ai_runs_locally ? (
              <span className="flex items-center gap-2">
                Local model (Ollama) <Badge tone="green">CVs stay on this server</Badge>
              </span>
            ) : (
              "Anthropic Claude"
            )}
          </Row>
          <Row icon={<Cpu />} label="Scoring engine">
            <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">{policy.scoring_engine}</code>
          </Row>
          <Row icon={<ShieldCheck />} label="Talent-pool consent required">
            {policy.talent_pool_consent_required ? "Yes" : "No"}
          </Row>
        </div>
      </Card>

      <Card title="Data protection" description="Retention and encryption of candidate data.">
        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
          <Row icon={<Lock />} label="Documents encrypted at rest">
            {policy.documents_encrypted ? <Badge tone="green">On</Badge> : <Badge tone="amber">Off: set DOCUMENT_ENCRYPTION_KEYS</Badge>}
          </Row>
          <Row icon={<Clock />} label="CV files kept">
            {policy.document_retention_days} days
          </Row>
          <Row icon={<Clock />} label="Inactive profiles kept (without consent)">
            {policy.candidate_retention_days} days
          </Row>
        </div>
        <p className="mt-3 text-xs text-zinc-500">
          See the <Link href="/privacy" className="font-medium text-brand-600 hover:underline dark:text-brand-400">candidate notice</Link> and the{" "}
          <Link href="/audit" className="font-medium text-brand-600 hover:underline dark:text-brand-400">audit log</Link>.
        </p>
      </Card>

      <Card title="Team">
        <Row icon={<Users />} label="Accounts and roles">
          <Badge>Not available yet</Badge>
        </Row>
        <p className="text-xs text-zinc-500">
          The platform currently runs in single-user mode: every action is recorded as &quot;recruiter&quot;. Sign-in and roles (recruiter,
          admin, data protection officer) are on the roadmap.
        </p>
      </Card>
    </div>
  );
}
