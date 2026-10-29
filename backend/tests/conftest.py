from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.extraction import ToolCallResult, ToolSpec

BACKEND = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    """A dedicated `<name>_test` database, created and migrated once per run, so tests never see dev data."""
    url = make_url(get_settings().database_url)
    test_url = url.set(database=f"{url.database}_test")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_url.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    except OperationalError:
        pytest.skip("Postgres is not reachable; run `docker compose up -d postgres`")
    finally:
        admin.dispose()

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.set_main_option("sqlalchemy.url", test_url.render_as_string(hide_password=False).replace("%", "%%"))
    command.upgrade(config, "head")

    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test; commits become savepoints."""
    connection = test_engine.connect()
    transaction = connection.begin()
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
