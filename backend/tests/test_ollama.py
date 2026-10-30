import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.agent.ollama_model import OllamaAgentModel, to_ollama_messages
from app.agent.tools import TOOLS
from app.config import Settings
from app.extraction import CANDIDATE_TARGET, LLMError, extract, tool_spec
from app.extraction.ollama_client import OllamaLLM, OllamaOptions, decoding_schema
from app.providers import make_agent_model, make_llm

CV = "SAMIRA BEN ALI\nData Engineer\nEXPERIENCE\nData Engineer at Acme\nSKILLS\nPython, SQL"


def client(handler: Callable[[dict[str, Any]], httpx.Response]) -> tuple[httpx.Client, list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return handler(body)

    return httpx.Client(transport=httpx.MockTransport(respond)), requests


def reply(content: str = "", tool_calls: list[dict[str, Any]] | None = None, **extra: Any) -> httpx.Response:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return httpx.Response(
        200,
        json={"model": "mistral", "message": message, "done_reason": "stop", "prompt_eval_count": 50, "eval_count": 9}
        | extra,
    )


def test_extraction_uses_structured_output_on_the_gpu() -> None:
    profile = {"identity": {"full_name": "Samira Ben Ali"}, "skills": [{"name": "Python", "evidence": "Python, SQL"}]}
    http, requests = client(lambda _: reply(json.dumps(profile)))
    result = extract(OllamaLLM(OllamaOptions(), client=http), CANDIDATE_TARGET, CV, max_repairs=1)

    assert result.profile.identity.full_name == "Samira Ben Ali"
    assert result.meta["model"] == "ollama/mistral"
    assert result.meta["input_tokens"] == 50
    body = requests[0]
    assert body["options"]["num_gpu"] == 99 and body["options"]["temperature"] == 0
    assert set(body["format"]["required"]) == set(body["format"]["properties"])
    assert "experiences" in body["format"]["required"]
    assert body["messages"][0]["role"] == "system" and "JSON schema" in body["messages"][0]["content"]


def test_extraction_correction_round_trip() -> None:
    replies = iter(['{"identity": {"linkedin_url": "not a url"}}', '{"identity": {"full_name": "Samira"}}'])
    http, requests = client(lambda _: reply(next(replies)))
    result = extract(OllamaLLM(OllamaOptions(), client=http), CANDIDATE_TARGET, CV, max_repairs=1)

    assert result.meta["llm_calls"] == 2
    feedback = requests[1]["messages"][-1]
    assert feedback["role"] == "user" and "linkedin_url" in feedback["content"]
    assert requests[1]["messages"][-2]["role"] == "assistant"


def test_invalid_json_counts_as_no_record() -> None:
    http, _ = client(lambda _: reply('{"identity": '))
    session = OllamaLLM(OllamaOptions(), client=http).session(system="s", tool=tool_spec(CANDIDATE_TARGET))
    assert session.start("doc").data is None


def test_decoding_schema_leaves_nested_fields_optional() -> None:
    schema = decoding_schema(tool_spec(CANDIDATE_TARGET).input_schema)
    assert "experiences" in schema["required"]
    assert schema["$defs"] == tool_spec(CANDIDATE_TARGET).input_schema["$defs"]


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(404, json={"error": "model not found"}), "not installed"),
        (httpx.Response(500, text="boom"), "Ollama error 500"),
    ],
)
def test_http_errors_become_llm_errors(response: httpx.Response, message: str) -> None:
    http, _ = client(lambda _: response)
    session = OllamaLLM(OllamaOptions(), client=http).session(system="s", tool=tool_spec(CANDIDATE_TARGET))
    with pytest.raises(LLMError, match=message):
        session.start("doc")


def test_unreachable_ollama_is_an_llm_error() -> None:
    def refuse(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    http = httpx.Client(transport=httpx.MockTransport(refuse))
    with pytest.raises(LLMError, match="is it running"):
        OllamaLLM(OllamaOptions(), client=http).session(system="s", tool=tool_spec(CANDIDATE_TARGET)).start("doc")


def test_agent_tool_calls_are_converted_to_tool_use_blocks() -> None:
    http, requests = client(
        lambda _: reply("Let me look.", [{"function": {"name": "list_jobs", "arguments": {"status": "open"}}}])
    )
    turn = OllamaAgentModel(OllamaOptions(), client=http).respond(
        system="sys", tools=[t.spec() for t in TOOLS.values()], messages=[{"role": "user", "content": "Jobs?"}]
    )

    assert turn.stop_reason == "tool_use"
    assert turn.content[0] == {"type": "text", "text": "Let me look."}
    tool_use = turn.content[1]
    assert tool_use["type"] == "tool_use" and tool_use["name"] == "list_jobs"
    assert tool_use["input"] == {"status": "open"} and tool_use["id"].startswith("toolu_local_")
    assert turn.model == "ollama/mistral"
    sent = requests[0]
    assert {t["function"]["name"] for t in sent["tools"]} == set(TOOLS)
    assert sent["messages"][0] == {"role": "system", "content": "sys"}


def test_agent_final_answer_and_truncation() -> None:
    http, _ = client(lambda _: reply("Done."))
    model = OllamaAgentModel(OllamaOptions(), client=http)
    assert model.respond(system="s", tools=[], messages=[]).stop_reason == "end_turn"

    http, _ = client(lambda _: reply("Cut", done_reason="length"))
    model = OllamaAgentModel(OllamaOptions(), client=http)
    assert model.respond(system="s", tools=[], messages=[]).stop_reason == "max_tokens"


def test_stored_history_is_converted_to_ollama_messages() -> None:
    history: list[dict[str, Any]] = [
        {"role": "user", "content": "Rank candidates"},
        {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "", "signature": "x"},
                {"type": "text", "text": "Checking."},
                {"type": "tool_use", "id": "t1", "name": "list_jobs", "input": {}},
                {"type": "tool_use", "id": "t2", "name": "get_job", "input": {"job_id": "j"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "[]"},
                {"type": "tool_result", "tool_use_id": "t2", "content": "not found", "is_error": True},
            ],
        },
    ]
    messages = to_ollama_messages("sys", history)

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool", "tool"]
    assert messages[2]["content"] == "Checking."
    assert [c["function"]["name"] for c in messages[2]["tool_calls"]] == ["list_jobs", "get_job"]
    assert messages[3] == {"role": "tool", "content": "[]", "tool_name": "list_jobs"}
    assert messages[4]["content"] == "ERROR: not found" and messages[4]["tool_name"] == "get_job"


def test_provider_factory() -> None:
    assert type(make_llm(Settings(llm_provider="ollama"))).__name__ == "OllamaLLM"
    assert type(make_llm(Settings(llm_provider="anthropic"))).__name__ == "AnthropicLLM"
    assert type(make_agent_model(Settings(llm_provider="ollama"))).__name__ == "OllamaAgentModel"
    assert type(make_agent_model(Settings(llm_provider="anthropic"))).__name__ == "AnthropicAgentModel"
