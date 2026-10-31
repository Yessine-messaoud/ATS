"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { ArrowUp, Check, CircleAlert, EyeOff, Plus, Sparkles, Wrench, X } from "lucide-react";

import { decideAgentActions, sendAgentMessage, type ConversationResult } from "@/app/actions";
import { Markdown } from "@/components/markdown";
import { Badge, Button, ButtonLink, Notice, cx } from "@/components/ui";
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

function Thinking() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div role="status" className="flex items-center gap-2 text-xs text-zinc-500">
      <span className="flex gap-1" aria-hidden>
        {[0, 150, 300].map((delay) => (
          <span key={delay} className="size-1.5 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: `${delay}ms` }} />
        ))}
      </span>
      Working… {seconds}s
    </div>
  );
}

export function Chat({ initial, firstPrompt }: { initial: Conversation; firstPrompt?: string }) {
  const router = useRouter();
  const [conversation, setConversation] = useState(initial);
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState<string>();
  const [error, setError] = useState<string>();
  const [choices, setChoices] = useState<Record<string, boolean>>({});
  const [pending, startTransition] = useTransition();
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const autoSent = useRef(false);
  const items = conversation.transcript as Item[];
  const actions = conversation.pending_actions;

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [items.length, actions.length, pending]);

  const apply = (result: ConversationResult) => {
    setError(result.error);
    setSent(undefined);
    if (result.conversation) setConversation(result.conversation);
  };

  const send = (value: string) => {
    const text = value.trim();
    if (!text || pending) return;
    setDraft("");
    setSent(text);
    startTransition(async () => apply(await sendAgentMessage(conversation.id, text)));
  };

  useEffect(() => {
    if (firstPrompt && !autoSent.current) {
      autoSent.current = true;
      router.replace(`/assistant/${conversation.id}`, { scroll: false });
      send(firstPrompt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstPrompt]);

  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }, [draft]);

  const submitDecisions = () =>
    startTransition(async () => {
      const decisions = actions.map((a) => ({ tool_use_id: a.tool_use_id, approved: choices[a.tool_use_id] ?? false }));
      apply(await decideAgentActions(conversation.id, decisions));
      setChoices({});
    });

  return (
    <div className="mx-auto flex max-w-3xl flex-col">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-semibold">Assistant</h1>
          {conversation.blind && (
            <Badge tone="indigo">
              <EyeOff className="size-3" aria-hidden /> blind screening
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          {typeof conversation.usage.calls === "number" && <span>{conversation.usage.calls} model call(s)</span>}
          <ButtonLink href="/assistant" size="sm" icon={<Plus className="size-3.5" />}>
            New
          </ButtonLink>
        </div>
      </div>

      <div className="space-y-4 pb-4">
        {items.length === 0 && !sent && (
          <div className="rounded-xl border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500 dark:border-zinc-700">
            <Sparkles className="mx-auto mb-2 size-5 text-indigo-500" aria-hidden />
            Ask a question to get started.
          </div>
        )}
        {items.map((item, index) =>
          item.role === "tool" ? (
            <p key={index} className="flex items-center gap-1.5 pl-1 text-xs text-zinc-500">
              <Wrench className="size-3" aria-hidden /> {TOOL_LABELS[item.tool ?? ""] ?? item.tool}
            </p>
          ) : item.role === "tool_error" ? (
            <p key={index} className="flex items-center gap-1.5 pl-1 text-xs text-amber-700 dark:text-amber-400">
              <CircleAlert className="size-3" aria-hidden /> {item.text}
            </p>
          ) : item.role === "user" ? (
            <div key={index} className="flex justify-end">
              <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2 text-sm text-white">
                {item.text}
              </div>
            </div>
          ) : (
            <div key={index} className="flex gap-3">
              <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-300">
                <Sparkles className="size-3.5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border border-zinc-200 bg-white px-4 py-3 text-sm shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
                <Markdown>{item.text ?? ""}</Markdown>
              </div>
            </div>
          ),
        )}
        {sent && (
          <div className="flex justify-end">
            <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-indigo-600/80 px-4 py-2 text-sm text-white">{sent}</div>
          </div>
        )}
        {pending && <Thinking />}
      </div>

      {actions.length > 0 && (
        <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50/60 p-4 dark:border-amber-800 dark:bg-amber-950/30">
          <h2 className="text-sm font-semibold">Confirm the proposed actions</h2>
          <p className="mb-3 text-xs text-zinc-500">Nothing changes until you submit. Every action is recorded in the audit log.</p>
          <ul className="space-y-2 text-sm">
            {actions.map((action) => (
              <li key={action.tool_use_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white px-3 py-2 dark:bg-zinc-900">
                <span>{action.summary}</span>
                <span className="flex gap-1" role="radiogroup" aria-label={action.summary}>
                  <Button
                    size="sm"
                    variant={choices[action.tool_use_id] === true ? "primary" : "secondary"}
                    role="radio"
                    aria-checked={choices[action.tool_use_id] === true}
                    icon={<Check className="size-3.5" />}
                    onClick={() => setChoices({ ...choices, [action.tool_use_id]: true })}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant={choices[action.tool_use_id] === false ? "danger" : "secondary"}
                    role="radio"
                    aria-checked={choices[action.tool_use_id] === false}
                    icon={<X className="size-3.5" />}
                    onClick={() => setChoices({ ...choices, [action.tool_use_id]: false })}
                  >
                    Decline
                  </Button>
                </span>
              </li>
            ))}
          </ul>
          <Button
            className="mt-3"
            loading={pending}
            disabled={actions.some((a) => choices[a.tool_use_id] === undefined)}
            onClick={submitDecisions}
          >
            Submit decisions
          </Button>
        </div>
      )}

      {error && (
        <div className="mb-3">
          <Notice tone="red" icon={<CircleAlert />}>
            {error}
          </Notice>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
        className="sticky bottom-4 flex items-end gap-2 rounded-2xl border border-zinc-200 bg-white p-2 shadow-lg dark:border-zinc-800 dark:bg-zinc-900"
      >
        <textarea
          ref={textarea}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
          rows={1}
          aria-label="Message"
          placeholder={actions.length ? "Sending a message declines the pending actions…" : "Ask the assistant… (Enter to send, Shift+Enter for a new line)"}
          className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-zinc-400"
        />
        <button
          type="submit"
          disabled={pending || !draft.trim()}
          aria-label="Send"
          className={cx(
            "flex size-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-500 disabled:opacity-40",
          )}
        >
          <ArrowUp className="size-4" />
        </button>
      </form>
      <div ref={bottom} />
    </div>
  );
}
