from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pymupdf
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import get_engine
from app.extraction import ToolCallResult, ToolSpec


@pytest.fixture
def db() -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test; commits become savepoints."""
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres is not reachable; run `docker compose up -d postgres` and `alembic upgrade head`")

    transaction = connection.begin()
    connection.execute(text("SELECT 1 FROM alembic_version"))
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@dataclass
class FakeSession:
    responses: list[dict[str, Any] | None]
    prompts: list[str] = field(default_factory=list)

    def _next(self) -> ToolCallResult:
        if not self.responses:
            raise AssertionError("FakeLLM ran out of scripted responses")
        return ToolCallResult(data=self.responses.pop(0), model="fake-model", input_tokens=100, output_tokens=50)

    def start(self, document_prompt: str) -> ToolCallResult:
        self.prompts.append(document_prompt)
        return self._next()

    def correct(self, feedback: str) -> ToolCallResult:
        self.prompts.append(feedback)
        return self._next()


@dataclass
class FakeLLM:
    """Returns scripted tool inputs in order; None simulates an answer without a tool call."""

    responses: list[dict[str, Any] | None]
    sessions: list[FakeSession] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)

    def session(self, *, system: str, tool: ToolSpec) -> FakeSession:
        self.tools.append(tool)
        fake = FakeSession(self.responses)
        self.sessions.append(fake)
        return fake


def make_pdf(lines: list[str], *, hidden: list[tuple[str, dict[str, Any]]] = ()) -> bytes:  # type: ignore[assignment]
    """Build a one-page PDF: visible lines, plus hidden spans given as (text, insert_text kwargs)."""
    document = pymupdf.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 16), line, fontsize=11)
    for hidden_text, options in hidden:
        page.insert_text(options.pop("point", (72, 700)), hidden_text, **options)
    data: bytes = document.tobytes()
    document.close()
    return data
