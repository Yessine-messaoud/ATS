import type { Metadata } from "next";

import { startConversation } from "@/app/actions";
import { Button, Card } from "@/components/ui";

export const metadata: Metadata = { title: "Assistant" };

const EXAMPLES = [
  "Who are the top 3 candidates for the Data Engineer job, and why?",
  "Is there a better opportunity than the Data Engineer job for Youssef Trabelsi?",
  "Prepare interview questions for Amira Gharbi for the Data Engineer role.",
  "Rédige un email de refus bienveillant pour Karim Mansour pour le stage PFE.",
];

export default function AssistantPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Card title="Recruitment assistant">
        <div className="space-y-3 text-sm text-zinc-600 dark:text-zinc-400">
          <p>
            Ask in plain language: rank candidates, explain a score, compare profiles, find better opportunities, prepare
            interviews, draft emails, or update a pipeline.
          </p>
          <p>
            The assistant uses the same scoring engine as the ranking pages and never invents scores. It never changes
            anything without your confirmation, and it refuses to filter candidates on protected characteristics.
          </p>
          <ul className="list-disc pl-5">
            {EXAMPLES.map((example) => (
              <li key={example}>{example}</li>
            ))}
          </ul>
        </div>
        <form action={startConversation} className="mt-4 flex items-center gap-4">
          <Button type="submit">Start a conversation</Button>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="blind" /> Blind screening (hide candidate names)
          </label>
        </form>
      </Card>
    </div>
  );
}
