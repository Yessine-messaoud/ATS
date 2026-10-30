import type { Metadata } from "next";

import { connection } from "next/server";

import { Card } from "@/components/ui";
import { request } from "@/lib/api";
import type { components } from "@/lib/api-types";

export const metadata: Metadata = { title: "How your application is processed" };

type Policy = components["schemas"]["PrivacyPolicyOut"];

function months(days: number): string {
  return days >= 60 ? `${Math.round(days / 30)} months` : `${days} days`;
}

/**
 * Candidate-facing transparency notice (GDPR art. 13-14 and 22; EU AI Act transparency for high-risk recruitment
 * systems). Its retention periods and AI set-up are read from the running configuration, so it cannot drift.
 */
export default async function PrivacyNoticePage() {
  await connection();
  const policy = await request<Policy>("/api/privacy/policy");

  return (
    <article className="mx-auto max-w-3xl space-y-4 text-sm leading-relaxed">
      <header>
        <h1 className="text-xl font-semibold">How your application is processed</h1>
        <p className="text-zinc-500">
          Information for candidates. The recruiting organisation is responsible for this processing (data controller).
        </p>
      </header>

      <Card title="What we use">
        <ul className="list-disc space-y-1 pl-5">
          <li>The CV or application you send us, and the information it contains about your experience, skills, education and languages.</li>
          <li>Your contact details, only to contact you about your application.</li>
          <li>
            We do <strong>not</strong> use your age, gender, nationality, family situation, religion, health or photo, even if
            your CV mentions them. They are removed automatically and never enter any assessment.
          </li>
        </ul>
      </Card>

      <Card title="How AI is used">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            An AI model reads your CV and turns it into a structured profile.{" "}
            {policy.ai_runs_locally
              ? "The model runs on the organisation's own servers: your CV is not sent to an AI provider."
              : "The model is provided by Anthropic (Claude), which processes your CV on the organisation's behalf and does not use it for training."}{" "}
            Every item it extracts is checked against the text of your CV, and a recruiter reviews anything that cannot be found there.
          </li>
          <li>
            Your profile is compared with the job&apos;s requirements by a <strong>deterministic scoring engine</strong> (
            {policy.scoring_engine}), not by the AI. The same profile always gets the same score, and each score comes with its
            breakdown: which requirements are met, which are missing, and why.
          </li>
          <li>
            <strong>No decision is made automatically.</strong> Scores help recruiters prioritise; a person reviews your application
            and takes every decision (shortlisting, rejection, offer). Each decision is recorded.
          </li>
          <li>Recruiters can review applications in blind mode, which hides names during screening.</li>
          <li>The system is tested so that names, gendered job titles and personal characteristics do not change any score.</li>
        </ul>
      </Card>

      <Card title="How long we keep your data">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            The file you sent is deleted after {months(policy.document_retention_days)}
            {policy.documents_encrypted ? "; until then it is stored encrypted" : ""}.
          </li>
          <li>
            Your profile is deleted after {months(policy.candidate_retention_days)} without activity, unless you agreed to stay in
            our talent pool.
          </li>
          <li>
            {policy.talent_pool_consent_required
              ? "Without your consent, your profile is only considered for the jobs you applied to."
              : "If you agree to join our talent pool, we may contact you about other suitable jobs. You can withdraw at any time."}
          </li>
        </ul>
      </Card>

      <Card title="Your rights">
        <p>
          You can ask the recruiter who contacted you, at any time and free of charge, to:
        </p>
        <ul className="mt-1 list-disc space-y-1 pl-5">
          <li>receive a copy of all the data held about you, including your scores and their explanations (machine-readable);</li>
          <li>correct inaccurate information in your profile;</li>
          <li>have your data erased;</li>
          <li>withdraw your talent-pool consent, or object to the processing;</li>
          <li>have your application reviewed by a person and get an explanation of an assessment.</li>
        </ul>
        <p className="mt-2 text-zinc-500">
          You can also lodge a complaint with your data protection authority (in Tunisia, the INPDP; in France, the CNIL).
        </p>
      </Card>
    </article>
  );
}
