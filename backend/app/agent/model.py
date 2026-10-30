"""Provider-neutral chat model interface for the agent, and its Claude implementation.

The loop is written by hand (not the SDK tool runner) because a turn can pause for a recruiter's confirmation
across HTTP requests: the conversation is stored as JSON and resumed later.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol, cast

import anthropic
from anthropic.types.beta import BetaMessageParam, BetaOutputConfigParam, BetaToolParam

from app.extraction.llm import LLMError, LLMRefused, ToolSpec

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class ModelTurn:
    content: list[dict[str, Any]]
    """Assistant content blocks as plain JSON (text, tool_use, thinking), stored and replayed unchanged."""
    stop_reason: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class AgentModel(Protocol):
    def respond(self, *, system: str, tools: list[ToolSpec], messages: list[dict[str, Any]]) -> ModelTurn: ...


class AnthropicAgentModel:
    def __init__(self, *, model: str, effort: str, max_tokens: int, client: anthropic.Anthropic | None = None):
        self._client = client
        self._model = model
        self._effort = effort
        self._max_tokens = max_tokens

    def respond(self, *, system: str, tools: list[ToolSpec], messages: list[dict[str, Any]]) -> ModelTurn:
        if self._client is None:
            try:
                self._client = anthropic.Anthropic()
            except anthropic.CredentialsError as exc:
                raise LLMError(f"LLM credentials are misconfigured: {exc}") from exc
        tool_params: list[BetaToolParam] = [
            {"name": t.name, "description": t.description, "input_schema": cast(Any, t.input_schema)} for t in tools
        ]
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
                system=system,
                tools=tool_params,
                tool_choice={"type": "auto"},
                messages=cast(list[BetaMessageParam], messages),
            )
        except anthropic.AuthenticationError as exc:
            raise LLMError("LLM credentials are missing or invalid") from exc
        except TypeError as exc:
            raise LLMError(f"LLM credentials are not configured: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("LLM rate limit reached; retry later") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"LLM API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("could not reach the LLM API") from exc
        if response.stop_reason == "refusal":
            raise LLMRefused("the model declined this request")
        usage = response.usage
        return ModelTurn(
            content=cast(list[dict[str, Any]], response.to_dict()["content"]),
            stop_reason=response.stop_reason or "end_turn",
            model=response.model,
            input_tokens=usage.input_tokens
            + (usage.cache_read_input_tokens or 0)
            + (usage.cache_creation_input_tokens or 0),
            output_tokens=usage.output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
