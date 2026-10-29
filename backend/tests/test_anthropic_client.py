"""AnthropicLLM request shape and conversation handling, against a stubbed SDK client."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.extraction import LLMError, LLMRefused, ToolSpec
from app.extraction.anthropic_client import AnthropicLLM

TOOL = ToolSpec(name="record_candidate_profile", description="Record it.", input_schema={"type": "object"})


def response(*, tool_input: dict[str, Any] | None, stop_reason: str = "tool_use") -> SimpleNamespace:
    content = [SimpleNamespace(type="thinking", thinking="")]
    if tool_input is not None:
        content.append(SimpleNamespace(type="tool_use", id="toolu_1", name=TOOL.name, input=tool_input))
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        model="claude-opus-5-5",
        usage=SimpleNamespace(
            input_tokens=10, output_tokens=5, cache_read_input_tokens=100, cache_creation_input_tokens=0
        ),
        _request_id="req_1",
    )


class StubClient:
    def __init__(self, *responses: SimpleNamespace) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses = list(responses)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        # Snapshot the messages: the session keeps appending to the same list.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses.pop(0)


def make_llm(client: StubClient) -> AnthropicLLM:
    return AnthropicLLM(model="claude-opus-5-5", effort="medium", max_tokens=16000, client=client)  # type: ignore[arg-type]


def test_request_uses_model_effort_fallbacks_caching_and_auto_tool_choice() -> None:
    client = StubClient(response(tool_input={"skills": []}))

    result = make_llm(client).session(system="sys", tool=TOOL).start("<document>...</document>")

    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"] == {"effort": "medium"}
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["cache_control"] == {"type": "ephemeral"}
    assert call["tool_choice"] == {"type": "auto"}
    assert "strict" not in call["tools"][0]
    assert result.data == {"skills": []}
    assert result.input_tokens == 110
    assert result.request_id == "req_1"


def test_correction_is_sent_as_error_tool_result_after_the_full_assistant_turn() -> None:
    first = response(tool_input={"bad": True})
    client = StubClient(first, response(tool_input={"skills": []}))
    session = make_llm(client).session(system="sys", tool=TOOL)

    session.start("doc")
    session.correct("field x is invalid")

    messages = client.calls[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[1]["content"] is first.content  # thinking + tool_use blocks passed back unchanged
    assert messages[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "field x is invalid", "is_error": True}
    ]


def test_correction_without_previous_tool_call_is_plain_text() -> None:
    client = StubClient(response(tool_input=None, stop_reason="end_turn"), response(tool_input={}))
    session = make_llm(client).session(system="sys", tool=TOOL)

    assert session.start("doc").data is None
    session.correct("call the tool")

    assert client.calls[1]["messages"][2] == {"role": "user", "content": "call the tool"}


@pytest.mark.parametrize("profile", [None, "broken"], ids=["no-credentials", "misconfigured-profile"])
def test_credential_problems_become_llm_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, profile: str | None
) -> None:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path))  # empty: no `ant auth login` profile
    if profile is not None:
        monkeypatch.setenv("ANTHROPIC_PROFILE", profile)
    llm = AnthropicLLM(model="claude-opus-5-5", effort="medium", max_tokens=16000)

    with pytest.raises(LLMError, match="credentials"):
        llm.session(system="sys", tool=TOOL).start("doc")


def test_refusal_raises() -> None:
    client = StubClient(response(tool_input=None, stop_reason="refusal"))

    with pytest.raises(LLMRefused):
        make_llm(client).session(system="sys", tool=TOOL).start("doc")
