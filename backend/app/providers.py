"""Build the configured LLM provider for extraction and for the assistant."""

from __future__ import annotations

from app.agent.model import AgentModel, AnthropicAgentModel
from app.agent.ollama_model import OllamaAgentModel
from app.config import Settings
from app.extraction.anthropic_client import AnthropicLLM
from app.extraction.llm import LLMClient
from app.extraction.ollama_client import OllamaLLM, OllamaOptions


def ollama_options(settings: Settings) -> OllamaOptions:
    return OllamaOptions(
        url=settings.ollama_url.rstrip("/"),
        model=settings.ollama_model,
        num_ctx=settings.ollama_num_ctx,
        num_gpu=settings.ollama_num_gpu,
        keep_alive=settings.ollama_keep_alive,
        timeout_s=settings.ollama_timeout_s,
    )


def make_llm(settings: Settings, *, effort: str | None = None) -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaLLM(ollama_options(settings))
    return AnthropicLLM(
        model=settings.llm_model, effort=effort or settings.llm_effort, max_tokens=settings.llm_max_tokens
    )


def make_agent_model(settings: Settings, *, effort: str | None = None) -> AgentModel:
    if settings.llm_provider == "ollama":
        return OllamaAgentModel(ollama_options(settings))
    return AnthropicAgentModel(
        model=settings.llm_model, effort=effort or settings.llm_effort, max_tokens=settings.llm_max_tokens
    )


def model_label(settings: Settings) -> str:
    return f"ollama/{settings.ollama_model}" if settings.llm_provider == "ollama" else settings.llm_model
