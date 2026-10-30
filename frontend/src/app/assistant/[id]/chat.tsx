"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useTransition } from "react";

import { decideAgentActions, sendAgentMessage, type ConversationResult } from "@/app/actions";
import { Badge, Button, Card, Notice, cx, inputClass } from "@/components/ui";
import type { components } from "@/lib/api-types";

type Conversation = components["schemas"]["ConversationOut"];
type Item = { role: string; text?: string; tool?: string };

const TOOL_LABELS: Record<string, string> = {
  list_jobs: "Listed jobs",
  search_candidates: "Searched the talent pool",
  get_candidate: "Read a candidate profile",
  get_job: "Read job requirements",
  rank_candidates_for_job: "Ranked candidates",
  explain_match: "Computed a score breakdown",
  interview_questions: "Prepared interview questions",
  recommend_jobs_for_candidate: "Looked for matching jobs",
  get_pipeline: "Read the pipeline",
  add_candidate_to_pipeline: "Proposed adding to a pipeline",
  move_application_stage: "Proposed a stage change",
};

export function Chat({ initial }: { initial: Conversation }) {
  const [conversation, setConversation] = useState(initial);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string>();
  const [choices, setChoices] = useState<Record<string, boolean>>({});
  const [pending, startTransition] = useTransition();
  const bottom = useRef<HTMLDivElement>(null);
  const items = conversation.transcript as Item[];
  const actions = conversation.pending_actions;

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [items.length, actions.length]);

  const apply = (result: ConversationResult) => {
    setError(result.error);
    if (result.conversation) setConversation(result.conversation);
  };

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    startTransition(async () => apply(await sendAgentMessage(conversation.id, text)));
  };

  const submitDecisions = () =>
    startTransition(async () => {
      const decisions = actions.map((a) => ({ tool_use_id: a.tool_use_id, approved: choices[a.tool_use_id] ?? false }));
      apply(await decideAgentActions(conversation.id, decisions));
      setChoices({});
    });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <Link href="/assistant" className="text-xs text-zinc-500 hover:underline">
          ← New conversation
        </Link>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          {conversation.blind && <Badge tone="blue">blind screening</Badge>}
          {typeof conversation.usage.calls === "number" && <span>{conversation.usage.calls} model call(s)</span>}
        </div>
      </div>

      <div className="space-y-3">
        {items.length === 0 && <p className="text-sm text-zinc-500">Ask a question to get started.</p>}
        {items.map((item, index) =>
          item.role === "tool" ? (
            <p key={index} className="pl-2 text-xs text-zinc-500">
              ⚙ {TOOL_LABELS[item.tool ?? ""] ?? item.tool}
            </p>
          ) : item.role === "tool_error" ? (
            <p key={index} className="pl-2 text-xs text-amber-700">
              ⚠ {item.text}
            </p>
          ) : (
            <div
              key={index}
              className={cx(
                "whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
                item.role === "user"
                  ? "ml-12 bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "mr-12 border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900",
              )}
            >
              {item.text}
            </div>
          ),
        )}
        {pending && <p className="pl-2 text-xs text-zinc-500">The assistant is working…</p>}
      </div>

      {actions.length > 0 && (
        <Card title="Confirm the proposed actions">
          <ul className="space-y-2 text-sm">
            {actions.map((action) => (
              <li key={action.tool_use_id} className="flex flex-wrap items-center justify-between gap-2">
                <span>{action.summary}</span>
                <span className="flex gap-1">
                  <Button
                    variant={choices[action.tool_use_id] === true ? "primary" : "secondary"}
                    className="px-2 py-0.5 text-xs"
                    onClick={() => setChoices({ ...choices, [action.tool_use_id]: true })}
                  >
                    Approve
                  </Button>
                  <Button
                    variant={choices[action.tool_use_id] === false ? "danger" : "secondary"}
                    className="px-2 py-0.5 text-xs"
                    onClick={() => setChoices({ ...choices, [action.tool_use_id]: false })}
                  >
                    Decline
                  </Button>
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center gap-3">
            <Button disabled={pending || actions.some((a) => choices[a.tool_use_id] === undefined)} onClick={submitDecisions}>
              Submit decisions
            </Button>
            <span className="text-xs text-zinc-500">Nothing changes until you submit. Every action is recorded in the audit log.</span>
          </div>
        </Card>
      )}

      {error && <Notice tone="red">{error}</Notice>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="flex gap-2"
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={2}
          placeholder={actions.length ? "Sending a message declines the pending actions…" : "Ask the assistant…"}
          className={inputClass}
        />
        <Button type="submit" disabled={pending || !draft.trim()}>
          Send
        </Button>
      </form>
      <div ref={bottom} />
    </div>
  );
}
