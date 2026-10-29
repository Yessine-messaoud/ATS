"""LLM-based structured extraction with validation, repair and evidence verification."""

from .extractor import CANDIDATE_TARGET, JOB_TARGET, ExtractionFailed, ExtractionResult, extract, tool_spec
from .llm import LLMClient, LLMError, LLMRefused, ToolCallResult, ToolSpec

__all__ = [
    "CANDIDATE_TARGET",
    "JOB_TARGET",
    "ExtractionFailed",
    "ExtractionResult",
    "LLMClient",
    "LLMError",
    "LLMRefused",
    "ToolCallResult",
    "ToolSpec",
    "extract",
    "tool_spec",
]
