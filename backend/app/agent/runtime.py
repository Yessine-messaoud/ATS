"""The agent loop, with recruiter confirmation for actions that change data.

A turn runs model → tools → model … until the model answers without calling tools. When it calls a tool that
requires confirmation, read-only calls from the same turn are executed, the others are stored as pending
actions, and the turn stops. The recruiter's decisions resume it: every tool_result of that turn is sent back
in a single user message, in the original order. The message history is append-only and replayed unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import AgentConversationRecord
from app.extraction.validation import format_errors

from .model import AgentModel, ModelTurn
from .policy import refusal
from .prompts import AGENT_PROMPT_VERSION, SYSTEM_PROMPT
from .tools import TOOLS, ToolContext, ToolError, describe_action

MAX_STEPS = 10
DECLINED = "The recruiter declined this action. Do not retry it unless they ask."
NOT_CONFIRMED = "Not confirmed: the recruiter sent a new message instead. Do not retry it unless they ask."
CUT_OFF = "Not executed: the response was cut off before the call was complete."


class NoPendingAction(ValueError):
    pass


@dataclass
class TurnStats:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    tool_calls: int = 0
    step_limit_reached: bool = False
    model: str | None = None


def _result(tool_use_id: str, content: str, *, is_error: bool = False) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block


def execute_tool(ctx: ToolContext, block: dict[str, Any]) -> dict[str, Any]:
    tool = TOOLS.get(block["name"])
    if tool is None:
        return _result(block["id"], f"Unknown tool {block['name']}.", is_error=True)
    try:
        args = tool.input_model.model_validate(block.get("input") or {})
    except ValidationError as exc:
        return _result(block["id"], f"Invalid input:\n{format_errors(exc)}", is_error=True)
    try:
        output = tool.run(ctx, args)
    except ToolError as exc:
        return _result(block["id"], str(exc), is_error=True)
    return _result(block["id"], json.dumps(output, default=str, ensure_ascii=False))


def _needs_confirmation(block: dict[str, Any]) -> bool:
    tool = TOOLS.get(block["name"])
    if tool is None or not tool.requires_confirmation:
        return False
    try:
        tool.input_model.model_validate(block.get("input") or {})
    except ValidationError:
        return False  # invalid input is reported back as an error, there is nothing to confirm
    return True


def _record(stats: TurnStats, turn: ModelTurn) -> None:
    stats.calls += 1
    stats.input_tokens += turn.input_tokens
    stats.output_tokens += turn.output_tokens
    stats.latency_ms += turn.latency_ms
    stats.model = turn.model


def run_loop(
    model: AgentModel, ctx: ToolContext, messages: list[dict[str, Any]], stats: TurnStats
) -> dict[str, Any] | None:
    """Advance the conversation in place. Returns the pending state when the recruiter must confirm actions."""
    specs = [tool.spec() for tool in TOOLS.values()]
    for _ in range(MAX_STEPS):
        turn = model.respond(system=SYSTEM_PROMPT, tools=specs, messages=messages)
        _record(stats, turn)
        messages.append({"role": "assistant", "content": turn.content})
        tool_uses = [b for b in turn.content if b.get("type") == "tool_use"]
        if not tool_uses:
            return None
        if turn.stop_reason != "tool_use":
            # Cut off mid-call: these calls still need results before the next user message.
            return {
                "order": [b["id"] for b in tool_uses],
                "results": [_result(b["id"], CUT_OFF, is_error=True) for b in tool_uses],
                "actions": [],
            }

        results, actions = [], []
        for block in tool_uses:
            if _needs_confirmation(block):
                actions.append(
                    {
                        "tool_use_id": block["id"],
                        "name": block["name"],
                        "input": block["input"],
                        "summary": describe_action(ctx, block["name"], block["input"]),
                    }
                )
            else:
                stats.tool_calls += 1
                results.append(execute_tool(ctx, block))
        if actions:
            return {"order": [b["id"] for b in tool_uses], "results": results, "actions": actions}
        messages.append({"role": "user", "content": results})
    stats.step_limit_reached = True
    return None


def _ordered(pending: dict[str, Any], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {r["tool_use_id"]: r for r in [*pending["results"], *extra]}
    return [by_id[i] for i in pending["order"] if i in by_id]


def _save(
    conversation: AgentConversationRecord,
    messages: list[dict[str, Any]],
    pending: dict[str, Any] | None,
    stats: TurnStats,
) -> None:
    usage = dict(conversation.usage or {})
    for key in ("calls", "input_tokens", "output_tokens", "latency_ms", "tool_calls"):
        usage[key] = usage.get(key, 0) + getattr(stats, key)
    usage["prompt_version"] = AGENT_PROMPT_VERSION
    if stats.model:
        usage["model"] = stats.model
    conversation.messages = list(messages)
    conversation.pending = pending
    conversation.usage = usage


def send_message(
    db: Session, model: AgentModel, ctx: ToolContext, conversation: AgentConversationRecord, text: str
) -> None:
    """Add a recruiter message and run the agent. Nothing is saved if the model call fails."""
    messages = list(conversation.messages)
    content: list[dict[str, Any]] = []
    if conversation.pending:
        declined = [_result(a["tool_use_id"], NOT_CONFIRMED) for a in conversation.pending["actions"]]
        content.extend(_ordered(conversation.pending, declined))
    content.append({"type": "text", "text": text})
    messages.append({"role": "user", "content": content})
    stats = TurnStats()
    if (refused := refusal(text)) is not None:
        # Protected-characteristic requests are refused by policy, without consulting the model.
        messages.append({"role": "assistant", "content": [{"type": "text", "text": refused}]})
        pending = None
    else:
        pending = run_loop(model, ctx, messages, stats)
    _save(conversation, messages, pending, stats)
    db.commit()


def decide(
    db: Session, model: AgentModel, ctx: ToolContext, conversation: AgentConversationRecord, approvals: dict[str, bool]
) -> None:
    """Apply the recruiter's decisions on pending actions, then let the agent continue."""
    pending = conversation.pending
    if not pending or not pending["actions"]:
        raise NoPendingAction("there is no action waiting for confirmation")
    missing = {a["tool_use_id"] for a in pending["actions"]} - approvals.keys()
    if missing:
        raise NoPendingAction(f"a decision is needed for every pending action (missing: {sorted(missing)})")

    resolved = []
    for action in pending["actions"]:
        if approvals[action["tool_use_id"]]:
            resolved.append(
                execute_tool(ctx, {"id": action["tool_use_id"], "name": action["name"], "input": action["input"]})
            )
        else:
            resolved.append(_result(action["tool_use_id"], DECLINED))
    messages = [*conversation.messages, {"role": "user", "content": _ordered(pending, resolved)}]
    # Save the executed actions first: if the model call below fails, they must not be executed twice.
    _save(conversation, messages, None, TurnStats(tool_calls=sum(approvals.values())))
    db.commit()

    stats = TurnStats()
    next_pending = run_loop(model, ctx, messages, stats)
    _save(conversation, messages, next_pending, stats)
    db.commit()


def transcript(conversation: AgentConversationRecord) -> list[dict[str, Any]]:
    """Display view of the history: recruiter and assistant text, plus the tools the assistant used."""
    items: list[dict[str, Any]] = []
    for message in conversation.messages:
        content = message["content"]
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        for block in blocks:
            kind = block.get("type")
            if kind == "text" and block.get("text", "").strip():
                items.append({"role": message["role"], "text": block["text"]})
            elif kind == "tool_use":
                items.append({"role": "tool", "tool": block["name"], "input": block.get("input", {})})
            elif kind == "tool_result" and block.get("is_error"):
                items.append({"role": "tool_error", "text": str(block.get("content"))})
    return items
