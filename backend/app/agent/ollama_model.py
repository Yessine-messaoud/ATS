"""Local agent model served by Ollama (the model must support tool calling, e.g. mistral, llama3.1, qwen2.5).

The runtime stores conversations in the Anthropic content-block format. This adapter converts that history to
Ollama's chat format on every call and converts the reply back, generating tool_use ids (Ollama has none), so the
runtime, the stored conversations and the confirmation flow are the same for both providers.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.extraction.llm import ToolSpec
from app.extraction.ollama_client import OllamaOptions, ollama_chat

from .model import ModelTurn


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content if block.get("type") == "text")
    return str(content)


def to_ollama_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            entry: dict[str, Any] = {"role": "assistant", "content": _text(blocks)}
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
                converted.append(
                    {"role": "tool", "content": result, "tool_name": tool_names.get(block["tool_use_id"], "")}
                )
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
        blocks.append(
            {
                "type": "tool_use",
                "id": f"toolu_local_{uuid.uuid4().hex[:20]}",
                "name": function.get("name", ""),
                "input": arguments,
            }
        )
    return blocks


class OllamaAgentModel:
    def __init__(self, options: OllamaOptions, client: httpx.Client | None = None):
        self._options = options
        self._client = client

    def respond(self, *, system: str, tools: list[ToolSpec], messages: list[dict[str, Any]]) -> ModelTurn:
        tool_params = [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
            }
            for t in tools
        ]
        body, latency_ms = ollama_chat(
            self._options, to_ollama_messages(system, messages), tools=tool_params, client=self._client
        )
        content = from_ollama_message(body.get("message") or {})
        if any(block["type"] == "tool_use" for block in content):
            stop_reason = "tool_use"
        elif body.get("done_reason") == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"
        if not content:
            content = [{"type": "text", "text": ""}]
        return ModelTurn(
            content=content,
            stop_reason=stop_reason,
            model=f"ollama/{body.get('model', self._options.model)}",
            input_tokens=int(body.get("prompt_eval_count") or 0),
            output_tokens=int(body.get("eval_count") or 0),
            latency_ms=latency_ms,
        )
