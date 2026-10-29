"""Provider-neutral interface for tool-based structured extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(RuntimeError):
    """The LLM call failed (credentials, network, rate limit, server error)."""


class LLMRefused(LLMError):
    """The model declined the request."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCallResult:
    data: dict[str, Any] | None
    """Tool input produced by the model, or None when it answered without calling the tool."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    request_id: str | None = None


class ExtractionSession(Protocol):
    """One append-only conversation: an initial request, then optional corrections."""

    def start(self, document_prompt: str) -> ToolCallResult: ...

    def correct(self, feedback: str) -> ToolCallResult:
        """Report a problem with the previous result and ask for a full corrected tool call."""
        ...


class LLMClient(Protocol):
    def session(self, *, system: str, tool: ToolSpec) -> ExtractionSession: ...
