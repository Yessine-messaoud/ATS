from types import SimpleNamespace
from typing import Any

import pytest
from anthropic.types.beta import BetaMessage

from app.agent.model import AnthropicAgentModel
from app.agent.tools import TOOLS
from app.extraction import LLMRefused


def message(stop_reason: str = "tool_use") -> BetaMessage:
    return BetaMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 4, "cache_read_input_tokens": 90},
            "content": [
                {"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "tool_use", "id": "toolu_1", "name": "list_jobs", "input": {}},
            ],
        }
    )


class Stub:
    def __init__(self, response: BetaMessage) -> None:
        self.calls: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._response = response

    def _create(self, **kwargs: Any) -> BetaMessage:
        self.calls.append(kwargs)
        return self._response


def test_request_shape_and_replayable_content() -> None:
    stub = Stub(message())
    model = AnthropicAgentModel(model="claude-opus-5-5", effort="medium", max_tokens=16000, client=stub)  # type: ignore[arg-type]

    turn = model.respond(
        system="sys", tools=[t.spec() for t in TOOLS.values()], messages=[{"role": "user", "content": "hi"}]
    )

    request = stub.calls[0]
    assert request["tool_choice"] == {"type": "auto"}  # forced tool use is rejected by this model
    assert request["fallbacks"] == "default" and request["cache_control"] == {"type": "ephemeral"}
    assert request["output_config"] == {"effort": "medium"}
    assert len(request["tools"]) == len(TOOLS) and all("strict" not in t for t in request["tools"])
    assert turn.content[0] == {"type": "thinking", "thinking": "", "signature": "sig"}  # passed back unchanged
    assert turn.stop_reason == "tool_use" and turn.input_tokens == 100


def test_refusal_raises() -> None:
    model = AnthropicAgentModel(model="m", effort="medium", max_tokens=100, client=Stub(message("refusal")))  # type: ignore[arg-type]

    with pytest.raises(LLMRefused):
        model.respond(system="s", tools=[], messages=[{"role": "user", "content": "x"}])
