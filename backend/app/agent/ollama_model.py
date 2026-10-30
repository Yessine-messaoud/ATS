"""Local agent model served by Ollama.

The runtime stores conversations in the Anthropic content-block format. This adapter converts that history to
Ollama's chat format on every call and converts the reply back, generating tool_use ids, so the runtime, the stored
conversations and the confirmation flow are the same for every provider.

Two ways to call tools:

- `native`: Ollama's tool calling. Needs a model trained for it, and many 7B models stop calling tools once they are
  offered more than a few (mistral 7B calls one tool reliably and none of eleven).
- `structured` (default): each step is split into small constrained decisions. A first call chooses the next step,
  one tool name or "answer", from an enum (JSON schema output); a second fills that tool's arguments under its input
  schema; an answer is written by a plain call. Tool calls and results are shown to the model as text. This works
  with any model, including ones without tool support (llama3), and arguments are always schema-valid.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Literal

import httpx

from app.extraction.llm import ToolSpec
from app.extraction.ollama_client import OllamaOptions, ollama_chat

from .model import ModelTurn

ToolMode = Literal["structured", "native"]
ANSWER = "answer"
# Tool calls in one turn after which the model must answer (the runtime's step limit is the hard stop).
MAX_TOOL_CALLS_PER_TURN = 6

ROUTER_PROMPT = """\
My request: "{request}"
Tools:
{catalogue}

{step} Ids (job_id, candidate_id, application_id) are only known from earlier tool results: look them up with \
list_jobs or search_candidates first, searching for the name or title I gave. Do only what I asked: never call a \
tool that changes data (adding to a pipeline, moving a stage) unless my request asks for that change."""
FIRST_STEP = """\
Nothing has been looked up yet. If my request must be refused (it asks to judge people on age, gender, origin, \
religion, family, health or another protected characteristic), "must_refuse" is true. Otherwise choose in "next" \
the tool that gets the information my request needs."""
NEXT_STEP = """\
{calls} tool(s) were already called for this request. If their results above contain what my request needs, \
"request_answered" is true and "next" is "answer". Otherwise choose the one tool that gets what is missing."""
ARGUMENTS_PROMPT = """\
Give the arguments for `{name}` ({description}) as JSON, for my request. Use ids exactly as they appear in earlier \
tool results."""
ANSWER_PROMPT = """\
Now answer my request "{request}". Write in the language of that request, use only facts from the tool results \
above, and do not describe tools or how to call them. If the request must be refused, explain briefly why. If an \
action is waiting for my confirmation, say so."""


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content if block.get("type") == "text")
    return str(content)


def to_ollama_messages(system: str, messages: list[dict[str, Any]], *, plain: bool = False) -> list[dict[str, Any]]:
    """Convert stored messages. With `plain`, tool calls and results become ordinary text turns."""
    converted: list[dict[str, Any]] = [{"role": "system", "content": system}]
    tool_names: dict[str, str] = {}
    for message in messages:
        content = message["content"]
        if message["role"] == "assistant":
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
            calls = []
            for block in blocks:
                if block.get("type") == "tool_use":
                    tool_names[block["id"]] = block["name"]
                    calls.append({"function": {"name": block["name"], "arguments": block.get("input") or {}}})
            text = _text(blocks)
            if plain:
                lines = [text] if text else []
                for c in calls:
                    arguments = json.dumps(c["function"]["arguments"], ensure_ascii=False)
                    lines.append(f"I call `{c['function']['name']}` with {arguments}.")
                converted.append({"role": "assistant", "content": "\n".join(lines)})
                continue
            entry: dict[str, Any] = {"role": "assistant", "content": text}
            if calls:
                entry["tool_calls"] = calls
            converted.append(entry)
            continue
        if isinstance(content, str):
            converted.append({"role": "user", "content": content})
            continue
        texts = []
        for block in content:
            if block.get("type") == "tool_result":
                result = _text(block.get("content", ""))
                if block.get("is_error"):
                    result = f"ERROR: {result}"
                name = tool_names.get(block["tool_use_id"], "")
                if plain:
                    texts.append(f"Result of `{name}`: {result}")
                else:
                    converted.append({"role": "tool", "content": result, "tool_name": name})
            elif block.get("type") == "text":
                texts.append(block["text"])
        if texts:
            converted.append({"role": "user", "content": "\n".join(texts)})
    return converted


def from_ollama_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if text := (message.get("content") or "").strip():
        blocks.append({"type": "text", "text": text})
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"_unparsed": arguments}
        blocks.append(_tool_use(function.get("name", ""), arguments))
    return blocks


def _tool_use(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": f"toolu_local_{uuid.uuid4().hex[:20]}", "name": name, "input": arguments}


def calls_this_turn(messages: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(tool name, canonical JSON arguments) of the tool calls made since the recruiter's last message."""
    calls: list[tuple[str, str]] = []
    for message in reversed(messages):
        content = message["content"]
        if message["role"] == "user" and (
            isinstance(content, str) or any(block.get("type") == "text" for block in content)
        ):
            break
        if message["role"] == "assistant" and isinstance(content, list):
            calls += [
                (block["name"], json.dumps(block.get("input") or {}, sort_keys=True))
                for block in content
                if block.get("type") == "tool_use"
            ]
    return calls


def tool_calls_this_turn(messages: list[dict[str, Any]]) -> int:
    return len(calls_this_turn(messages))


UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


def seen_ids(messages: list[dict[str, Any]]) -> set[str]:
    """Record ids that appeared in tool results or in the recruiter's own messages."""
    found: set[str] = set()
    for message in messages:
        if message["role"] == "user":
            found.update(UUID.findall(json.dumps(message["content"])))
    return found


def id_parameters(tool: ToolSpec) -> list[str]:
    return [name for name in tool.input_schema.get("properties", {}) if name.endswith("_id")]


def grounded_schema(tool: ToolSpec, known_ids: list[str]) -> dict[str, Any]:
    """The tool's input schema with every id parameter restricted to ids already seen in the conversation."""
    if not known_ids or not id_parameters(tool):
        return tool.input_schema
    properties = dict(tool.input_schema["properties"])
    for name in id_parameters(tool):
        properties[name] = {"type": "string", "enum": known_ids, "description": properties[name].get("description", "")}
    return {**tool.input_schema, "properties": properties}


def last_request(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        content = message["content"]
        if message["role"] != "user":
            continue
        if isinstance(content, str):
            return content
        text = "\n".join(block["text"] for block in content if block.get("type") == "text")
        if text:
            return text
    return ""


def catalogue(tools: list[ToolSpec]) -> str:
    lines = []
    for tool in tools:
        properties = tool.input_schema.get("properties", {})
        required = set(tool.input_schema.get("required", []))
        params = ", ".join(name if name in required else f"{name}?" for name in properties)
        lines.append(f"- {tool.name}({params}): {tool.description.splitlines()[0]}")
    return "\n".join(lines)


class OllamaAgentModel:
    def __init__(
        self, options: OllamaOptions, *, tool_mode: ToolMode = "structured", client: httpx.Client | None = None
    ):
        self._options = options
        self._tool_mode = tool_mode
        self._client = client

    def respond(self, *, system: str, tools: list[ToolSpec], messages: list[dict[str, Any]]) -> ModelTurn:
        if self._tool_mode == "native" or not tools:
            return self._native(system, tools, messages)
        return self._structured(system, tools, messages)

    def _turn(
        self, content: list[dict[str, Any]], stop_reason: str, bodies: list[dict[str, Any]], ms: int
    ) -> ModelTurn:
        return ModelTurn(
            content=content or [{"type": "text", "text": ""}],
            stop_reason=stop_reason,
            model=f"ollama/{bodies[-1].get('model', self._options.model)}",
            input_tokens=sum(int(b.get("prompt_eval_count") or 0) for b in bodies),
            output_tokens=sum(int(b.get("eval_count") or 0) for b in bodies),
            latency_ms=ms,
        )

    def _native(self, system: str, tools: list[ToolSpec], messages: list[dict[str, Any]]) -> ModelTurn:
        tool_params = [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
            }
            for t in tools
        ]
        body, latency_ms = ollama_chat(
            self._options, to_ollama_messages(system, messages), tools=tool_params or None, client=self._client
        )
        content = from_ollama_message(body.get("message") or {})
        if any(block["type"] == "tool_use" for block in content):
            stop_reason = "tool_use"
        elif body.get("done_reason") == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"
        return self._turn(content, stop_reason, [body], latency_ms)

    def _structured(self, system: str, tools: list[ToolSpec], messages: list[dict[str, Any]]) -> ModelTurn:
        history = to_ollama_messages(system, messages, plain=True)
        bodies: list[dict[str, Any]] = []
        elapsed = 0

        def call(prompt: str, schema: dict[str, Any] | None) -> str:
            nonlocal elapsed
            body, ms = ollama_chat(
                self._options, [*history, {"role": "user", "content": prompt}], format=schema, client=self._client
            )
            bodies.append(body)
            elapsed += ms
            return str((body.get("message") or {}).get("content") or "")

        known_ids = sorted(seen_ids(messages))
        # A tool that needs ids can only be called once some ids have been looked up.
        by_name = {tool.name: tool for tool in tools if known_ids or not id_parameters(tool)}
        choice = ANSWER
        calls_so_far = tool_calls_this_turn(messages)
        if calls_so_far < MAX_TOOL_CALLS_PER_TURN:
            # Before any lookup the model may refuse, but not answer: an answer would have no facts to stand on.
            done_flag, done_text = ("must_refuse", FIRST_STEP) if calls_so_far == 0 else ("request_answered", NEXT_STEP)
            router = {
                "type": "object",
                "properties": {
                    done_flag: {"type": "boolean"},
                    "next": {"type": "string", "enum": [*by_name] if calls_so_far == 0 else [ANSWER, *by_name]},
                },
                "required": [done_flag, "next"],
            }
            prompt = ROUTER_PROMPT.format(
                request=last_request(messages),
                step=done_text.format(calls=calls_so_far),
                catalogue=catalogue(list(by_name.values())),
            )
            try:
                decision = json.loads(call(prompt, router))
                choice = ANSWER if decision.get(done_flag) else str(decision.get("next", ANSWER))
            except (json.JSONDecodeError, AttributeError):
                choice = ANSWER

        if choice in by_name:
            tool = by_name[choice]
            schema = grounded_schema(tool, known_ids)
            raw = call(ARGUMENTS_PROMPT.format(name=tool.name, description=tool.description), schema)
            try:
                arguments = json.loads(raw)
            except json.JSONDecodeError:
                arguments = {"_unparsed": raw}  # reported back to the model as invalid input by the runtime
            if not isinstance(arguments, dict):
                arguments = {"_unparsed": arguments}
            # The same call again would return the same result: the model is looping, so it answers instead.
            if (tool.name, json.dumps(arguments, sort_keys=True)) not in calls_this_turn(messages):
                return self._turn([_tool_use(tool.name, arguments)], "tool_use", bodies, elapsed)

        answer = call(ANSWER_PROMPT.format(request=last_request(messages)), None).strip()
        stop_reason = "max_tokens" if bodies[-1].get("done_reason") == "length" else "end_turn"
        return self._turn([{"type": "text", "text": answer}], stop_reason, bodies, elapsed)
