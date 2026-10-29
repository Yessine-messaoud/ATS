"""Claude implementation of the extraction LLM interface.

The tool is deliberately *not* `strict`: strict schemas are limited to 24 optional and 16 union parameters, and the
canonical profiles exceed that. Tool inputs are always parsed JSON; schema conformance is enforced afterwards by
Pydantic, with a correction round-trip on failure.
"""

from __future__ import annotations

import time
from typing import Any, cast

import anthropic
from anthropic.types.beta import BetaMessageParam, BetaOutputConfigParam, BetaToolParam

from .llm import LLMError, LLMRefused, ToolCallResult, ToolSpec

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicSession:
    def __init__(
        self, client: anthropic.Anthropic, *, model: str, effort: str, max_tokens: int, system: str, tool: ToolSpec
    ):
        self._client = client
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens
        self._system = system
        self._tool = tool
        self._messages: list[dict[str, Any]] = []
        self._pending_tool_use_id: str | None = None

    def start(self, document_prompt: str) -> ToolCallResult:
        self._messages.append({"role": "user", "content": document_prompt})
        return self._call()

    def correct(self, feedback: str) -> ToolCallResult:
        if self._pending_tool_use_id is not None:
            content: Any = [
                {"type": "tool_result", "tool_use_id": self._pending_tool_use_id, "content": feedback, "is_error": True}
            ]
        else:
            content = feedback
        self._messages.append({"role": "user", "content": content})
        return self._call()

    def _call(self) -> ToolCallResult:
        tool: BetaToolParam = {
            "name": self._tool.name,
            "description": self._tool.description,
            "input_schema": cast(Any, self._tool.input_schema),
        }
        output_config: BetaOutputConfigParam = {"effort": cast(Any, self._effort)}
        started = time.perf_counter()
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config=output_config,
                cache_control={"type": "ephemeral"},
                system=self._system,
                tools=[tool],
                tool_choice={"type": "auto"},
                messages=cast(list[BetaMessageParam], self._messages),
            )
        except anthropic.AuthenticationError as exc:
            raise LLMError("LLM credentials are missing or invalid") from exc
        except TypeError as exc:
            # Raised while building the request when no credential source (API key, token, profile) resolves.
            raise LLMError(f"LLM credentials are not configured: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("LLM rate limit reached; retry later") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"LLM API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("could not reach the LLM API") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.stop_reason == "refusal":
            raise LLMRefused("the model declined to process this document")

        # Append the full content (thinking and tool_use blocks included) so the conversation stays append-only.
        self._messages.append({"role": "assistant", "content": response.content})
        tool_use = next(
            (block for block in response.content if block.type == "tool_use" and block.name == self._tool.name), None
        )
        self._pending_tool_use_id = tool_use.id if tool_use is not None else None
        return ToolCallResult(
            data=dict(tool_use.input) if tool_use is not None and isinstance(tool_use.input, dict) else None,
            model=response.model,
            input_tokens=response.usage.input_tokens
            + (response.usage.cache_read_input_tokens or 0)
            + (response.usage.cache_creation_input_tokens or 0),
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            request_id=response._request_id,
        )


class AnthropicLLM:
    def __init__(self, *, model: str, effort: str, max_tokens: int, client: anthropic.Anthropic | None = None):
        # Created lazily: credential resolution can fail, and that must surface as an LLMError, not at startup.
        self._client = client
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens

    def session(self, *, system: str, tool: ToolSpec) -> AnthropicSession:
        if self._client is None:
            try:
                self._client = anthropic.Anthropic()
            except anthropic.CredentialsError as exc:
                raise LLMError(f"LLM credentials are misconfigured: {exc}") from exc
        return AnthropicSession(
            self._client, model=self._model, effort=self._effort, max_tokens=self._max_tokens, system=system, tool=tool
        )
