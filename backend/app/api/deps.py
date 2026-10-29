"""Shared FastAPI dependencies and error mapping."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.extraction import ExtractionFailed, LLMClient, LLMError, LLMRefused
from app.extraction.anthropic_client import AnthropicLLM
from app.ingestion import RejectedFile, UnreadableDocument
from app.services.profiles import DuplicateDocument


@lru_cache
def get_llm() -> LLMClient:
    settings = get_settings()
    return AnthropicLLM(model=settings.llm_model, effort=settings.llm_effort, max_tokens=settings.llm_max_tokens)


DbSession = Annotated[Session, Depends(get_session)]
Llm = Annotated[LLMClient, Depends(get_llm)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@contextmanager
def domain_errors() -> Iterator[None]:
    """Translate ingestion, extraction and duplicate errors into HTTP responses."""
    try:
        yield
    except RejectedFile as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except UnreadableDocument as exc:
        raise HTTPException(422, str(exc)) from exc
    except DuplicateDocument as exc:
        raise HTTPException(409, {"message": str(exc), "existing_id": str(exc.existing_id)}) from exc
    except LLMRefused as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(503, f"extraction service unavailable: {exc}") from exc
    except ExtractionFailed as exc:
        raise HTTPException(502, f"extraction failed: {exc}") from exc


def get_or_404[T](getter: Callable[[], T | None], what: str) -> T:
    value = getter()
    if value is None:
        raise HTTPException(404, f"{what} not found")
    return value
