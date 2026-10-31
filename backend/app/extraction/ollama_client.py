"""Local-model implementation of the extraction LLM interface, served by Ollama.

Small local models call tools unreliably, so extraction uses Ollama's structured outputs instead: the tool's JSON
schema is passed as `format`, decoding is constrained to it, and the reply is the tool input. The schema is also
given in the system prompt, which grounds the model in the field meanings. Pydantic validation and the correction
round-trip still apply afterwards.

`num_gpu` is the number of layers offloaded to the GPU. Ollama's own estimate is conservative and leaves part of a
7B model on the CPU of a 6 GB card; a high value forces every layer onto the GPU, which is about 1.7x faster there.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .llm import LLMError, ToolCallResult, ToolSpec


@dataclass(frozen=True)
class OllamaOptions:
    url: str = "http://localhost:11434"
    model: str = "mistral"
    num_ctx: int = 8192
    num_gpu: int | None = 99
    temperature: float = 0.0
    keep_alive: str = "30m"
    timeout_s: float = 600.0


def ollama_chat(
    options: OllamaOptions,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    format: dict[str, Any] | None = None,
    max_tokens: int | None = None,
    client: httpx.Client | None = None,
) -> tuple[dict[str, Any], int]:
    """One non-streaming /api/chat call. Returns the response body and the latency in milliseconds.

    `max_tokens` caps the output: Ollama's default is unlimited, so a model that starts repeating itself would
    otherwise generate until the context is full (minutes per call on a laptop GPU).
    """
    model_options: dict[str, Any] = {"num_ctx": options.num_ctx, "temperature": options.temperature}
    if max_tokens is not None:
        model_options["num_predict"] = max_tokens
    if options.num_gpu is not None:
        model_options["num_gpu"] = options.num_gpu
    body: dict[str, Any] = {
        "model": options.model,
        "messages": messages,
        "stream": False,
        "keep_alive": options.keep_alive,
        "options": model_options,
    }
    if tools:
        body["tools"] = tools
    if format is not None:
        body["format"] = format

    started = time.perf_counter()
    try:
        if client is not None:
            response = client.post(f"{options.url}/api/chat", json=body, timeout=options.timeout_s)
        else:
            response = httpx.post(f"{options.url}/api/chat", json=body, timeout=options.timeout_s)
    except httpx.TimeoutException as exc:
        raise LLMError(f"the local model did not answer within {options.timeout_s:.0f}s") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"could not reach Ollama at {options.url}; is it running?") from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    if response.status_code == 404:
        raise LLMError(f"model {options.model!r} is not installed in Ollama (run `ollama pull {options.model}`)")
    if response.status_code >= 400:
        raise LLMError(f"Ollama error {response.status_code}: {response.text[:300]}")
    return response.json(), latency_ms


# A full CV profile is about 1-2k tokens of JSON; a cut-off reply is invalid JSON and goes to the correction round.
EXTRACTION_MAX_TOKENS = 4096


def decoding_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """The schema with every top-level property required.

    Under constrained decoding a small model tends to skip optional sections (experiences, education) entirely;
    requiring the keys makes it emit each one, as an empty list or null when the document has nothing for it.
    """
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return schema
    return {**schema, "required": list(properties)}


def schema_instructions(tool: ToolSpec) -> str:
    schema = json.dumps(tool.input_schema, separators=(",", ":"))
    return (
        f"\n\nOutput format: reply with one JSON object only, the input of `{tool.name}` "
        f"({tool.description}). It must follow this JSON schema:\n{schema}"
    )


class OllamaSession:
    def __init__(self, options: OllamaOptions, *, system: str, tool: ToolSpec, client: httpx.Client | None = None):
        self._options = options
        self._tool = tool
        self._client = client
        self._format = decoding_schema(tool.input_schema)
        self._messages: list[dict[str, Any]] = [{"role": "system", "content": system + schema_instructions(tool)}]

    def start(self, document_prompt: str) -> ToolCallResult:
        self._messages.append({"role": "user", "content": document_prompt})
        return self._call()

    def correct(self, feedback: str) -> ToolCallResult:
        self._messages.append({"role": "user", "content": feedback.replace("Call `", "Return the JSON for `")})
        return self._call()

    def _call(self) -> ToolCallResult:
        body, latency_ms = ollama_chat(
            self._options, self._messages, format=self._format, max_tokens=EXTRACTION_MAX_TOKENS, client=self._client
        )
        content = (body.get("message") or {}).get("content") or ""
        self._messages.append({"role": "assistant", "content": content})
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None  # e.g. cut off by the context limit; reported back as "did not call the tool"
        return ToolCallResult(
            data=parsed if isinstance(parsed, dict) else None,
            model=f"ollama/{body.get('model', self._options.model)}",
            input_tokens=int(body.get("prompt_eval_count") or 0),
            output_tokens=int(body.get("eval_count") or 0),
            latency_ms=latency_ms,
        )


class OllamaLLM:
    def __init__(self, options: OllamaOptions, client: httpx.Client | None = None):
        self._options = options
        self._client = client

    def session(self, *, system: str, tool: ToolSpec) -> OllamaSession:
        return OllamaSession(self._options, system=system, tool=tool, client=self._client)
