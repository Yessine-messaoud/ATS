import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import runtime
from app.agent.model import ModelTurn
from app.agent.runtime import DECLINED, NOT_CONFIRMED, NoPendingAction, decide, send_message, transcript
from app.agent.tools import AGENT_ACTOR, ToolContext
from app.api.agent import get_agent_model
from app.db import AgentConversationRecord, ApplicationRecord, AuditLogRecord, CandidateRecord, JobRecord, get_session
from app.extraction import LLMError, ToolSpec
from app.main import app
from scripts.seed_demo import seed


def text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def call(tool_id: str, name: str, **arguments: Any) -> dict[str, Any]:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": arguments}


@dataclass
class ScriptedModel:
    """Returns scripted assistant turns and records what it was sent."""

    turns: list[list[dict[str, Any]] | Exception]
    requests: list[list[dict[str, Any]]] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)

    def respond(self, *, system: str, tools: list[ToolSpec], messages: list[dict[str, Any]]) -> ModelTurn:
        self.requests.append(json.loads(json.dumps(messages)))
        self.tools = [t.name for t in tools]
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        stop = "tool_use" if any(b["type"] == "tool_use" for b in turn) else "end_turn"
        return ModelTurn(content=turn, stop_reason=stop, model="scripted", input_tokens=10, output_tokens=5)


@pytest.fixture
def demo(db: Session) -> dict[str, Any]:
    seed(db)
    jobs = {j.title: j for j in db.scalars(select(JobRecord))}
    candidates = {c.profile["identity"]["full_name"]: c for c in db.scalars(select(CandidateRecord))}
    return {"jobs": jobs, "candidates": candidates}


def conversation(db: Session, *, blind: bool = False) -> AgentConversationRecord:
    record = AgentConversationRecord(blind=blind, messages=[], usage={})
    db.add(record)
    db.flush()
    return record


def ctx(db: Session, *, blind: bool = False) -> ToolContext:
    return ToolContext(db=db, blind=blind, full_scoring_limit=500, retrieval_k=200)


def results(message: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["tool_use_id"]: b for b in message["content"] if b["type"] == "tool_result"}


def test_read_only_tools_run_automatically(db: Session, demo: dict[str, Any]) -> None:
    job = demo["jobs"]["Data Engineer"]
    model = ScriptedModel(
        [
            [text("Let me look."), call("t1", "list_jobs")],
            [call("t2", "rank_candidates_for_job", job_id=str(job.id), limit=3)],
            [text("Samira Ben Ali is the strongest match.")],
        ]
    )
    conv = conversation(db)

    send_message(db, model, ctx(db), conv, "Who are the best candidates for the Data Engineer job?")

    assert "add_candidate_to_pipeline" in model.tools
    ranking = json.loads(results(model.requests[2][-1])["t2"]["content"])
    assert ranking["ranked"][0]["name"] == "Samira Ben Ali"
    assert conv.pending is None
    assert conv.usage["calls"] == 3 and conv.usage["tool_calls"] == 2
    assert [i["role"] for i in transcript(conv)] == ["user", "assistant", "tool", "tool", "assistant"]


def test_actions_wait_for_confirmation_then_execute(db: Session, demo: dict[str, Any]) -> None:
    job, devops = demo["jobs"]["Data Engineer"], demo["candidates"]["Mehdi Jlassi"]
    model = ScriptedModel(
        [[call("t1", "add_candidate_to_pipeline", candidate_id=str(devops.id), job_id=str(job.id))], [text("Done.")]]
    )
    conv = conversation(db)

    send_message(db, model, ctx(db), conv, "Add Mehdi to the Data Engineer pipeline")

    assert conv.pending is not None and conv.pending["actions"][0]["summary"].startswith(
        "Add Mehdi Jlassi to the pipeline"
    )
    assert db.scalar(select(ApplicationRecord).where(ApplicationRecord.candidate_id == devops.id)) is None

    decide(db, model, ctx(db), conv, {"t1": True})

    assert db.scalar(select(ApplicationRecord).where(ApplicationRecord.candidate_id == devops.id)) is not None
    created = db.scalars(select(AuditLogRecord).where(AuditLogRecord.action == "application.created")).all()
    assert [a.actor for a in created] == [AGENT_ACTOR]
    assert model.requests[1][-1]["role"] == "user" and "t1" in results(model.requests[1][-1])
    assert conv.pending is None


def test_declined_action_is_not_executed(db: Session, demo: dict[str, Any]) -> None:
    job, devops = demo["jobs"]["Data Engineer"], demo["candidates"]["Mehdi Jlassi"]
    model = ScriptedModel(
        [[call("t1", "add_candidate_to_pipeline", candidate_id=str(devops.id), job_id=str(job.id))], [text("OK.")]]
    )
    conv = conversation(db)
    send_message(db, model, ctx(db), conv, "Add Mehdi")

    decide(db, model, ctx(db), conv, {"t1": False})

    assert db.scalar(select(ApplicationRecord).where(ApplicationRecord.candidate_id == devops.id)) is None
    assert results(model.requests[1][-1])["t1"]["content"] == DECLINED


def test_mixed_turn_runs_reads_and_keeps_result_order(db: Session, demo: dict[str, Any]) -> None:
    job, devops = demo["jobs"]["Data Engineer"], demo["candidates"]["Mehdi Jlassi"]
    model = ScriptedModel(
        [
            [
                call("t1", "get_job", job_id=str(job.id)),
                call("t2", "add_candidate_to_pipeline", candidate_id=str(devops.id), job_id=str(job.id)),
                call("t3", "list_jobs"),
            ],
            [text("Done.")],
        ]
    )
    conv = conversation(db)
    send_message(db, model, ctx(db), conv, "Check the job and add Mehdi")

    assert [a["tool_use_id"] for a in conv.pending["actions"]] == ["t2"]  # type: ignore[index]
    decide(db, model, ctx(db), conv, {"t2": True})

    sent = model.requests[1][-1]["content"]
    assert [b["tool_use_id"] for b in sent] == ["t1", "t2", "t3"]


def test_new_message_declines_pending_actions(db: Session, demo: dict[str, Any]) -> None:
    job, devops = demo["jobs"]["Data Engineer"], demo["candidates"]["Mehdi Jlassi"]
    model = ScriptedModel(
        [[call("t1", "add_candidate_to_pipeline", candidate_id=str(devops.id), job_id=str(job.id))], [text("Sure.")]]
    )
    conv = conversation(db)
    send_message(db, model, ctx(db), conv, "Add Mehdi")

    send_message(db, model, ctx(db), conv, "Actually, never mind")

    last = model.requests[1][-1]["content"]
    assert last[0]["content"] == NOT_CONFIRMED and last[1] == text("Actually, never mind")
    with pytest.raises(NoPendingAction):
        decide(db, model, ctx(db), conv, {"t1": True})


def test_invalid_input_and_unknown_tool_are_reported_as_errors(db: Session, demo: dict[str, Any]) -> None:
    model = ScriptedModel(
        [
            [call("t1", "add_candidate_to_pipeline", candidate_id="not-a-uuid"), call("t2", "delete_everything")],
            [text("Sorry.")],
        ]
    )
    conv = conversation(db)

    send_message(db, model, ctx(db), conv, "Do it")

    sent = results(model.requests[1][-1])
    assert sent["t1"]["is_error"] and "Invalid input" in sent["t1"]["content"]
    assert sent["t2"]["is_error"] and "Unknown tool" in sent["t2"]["content"]
    assert conv.pending is None


def test_tool_outputs_never_contain_contact_details_and_honour_blind_mode(db: Session, demo: dict[str, Any]) -> None:
    samira, job = demo["candidates"]["Samira Ben Ali"], demo["jobs"]["Data Engineer"]
    calls = [
        call("t1", "get_candidate", candidate_id=str(samira.id)),
        call("t2", "rank_candidates_for_job", job_id=str(job.id)),
        call("t3", "search_candidates", query="data engineer spark"),
        call("t4", "get_pipeline", job_id=str(job.id)),
    ]
    model = ScriptedModel([calls, [text("ok")]])
    conv = conversation(db, blind=True)

    send_message(db, model, ctx(db, blind=True), conv, "Tell me about the candidates")

    outputs = " ".join(r["content"] for r in results(model.requests[1][-1]).values())
    assert "@example.com" not in outputs and "+216" not in outputs
    for name in demo["candidates"]:
        assert name not in outputs
    assert "Candidate " in outputs


def test_model_failure_saves_nothing_on_send_but_keeps_executed_actions(db: Session, demo: dict[str, Any]) -> None:
    job, devops = demo["jobs"]["Data Engineer"], demo["candidates"]["Mehdi Jlassi"]
    conv = conversation(db)
    with pytest.raises(LLMError):
        send_message(db, ScriptedModel([LLMError("down")]), ctx(db), conv, "hello")
    assert conv.messages == []

    model = ScriptedModel(
        [[call("t1", "add_candidate_to_pipeline", candidate_id=str(devops.id), job_id=str(job.id))], LLMError("down")]
    )
    send_message(db, model, ctx(db), conv, "Add Mehdi")
    with pytest.raises(LLMError):
        decide(db, model, ctx(db), conv, {"t1": True})

    assert db.scalar(select(ApplicationRecord).where(ApplicationRecord.candidate_id == devops.id)) is not None
    assert conv.pending is None and conv.messages[-1]["role"] == "user"  # executed result is stored, not re-run


def test_cut_off_tool_call_gets_an_error_result(db: Session, demo: dict[str, Any]) -> None:
    class CutOff(ScriptedModel):
        def respond(self, **kwargs: Any) -> ModelTurn:
            turn = super().respond(**kwargs)
            if len(self.requests) == 1:
                turn.stop_reason = "max_tokens"
            return turn

    model = CutOff([[call("t1", "list_jobs")], [text("ok")]])
    conv = conversation(db)
    send_message(db, model, ctx(db), conv, "jobs?")
    send_message(db, model, ctx(db), conv, "again")

    first = model.requests[1][-1]["content"][0]
    assert first["tool_use_id"] == "t1" and first["is_error"]


def test_step_limit_stops_runaway_loops(db: Session, demo: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "MAX_STEPS", 3)
    model = ScriptedModel([[call(f"t{i}", "list_jobs")] for i in range(3)])
    conv = conversation(db)

    send_message(db, model, ctx(db), conv, "loop")

    assert len(model.requests) == 3
    assert conv.pending is None


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_conversation_flow(client: TestClient, demo: dict[str, Any]) -> None:
    job, devops = demo["jobs"]["Data Engineer"], demo["candidates"]["Mehdi Jlassi"]
    model = ScriptedModel(
        [[call("t1", "add_candidate_to_pipeline", candidate_id=str(devops.id), job_id=str(job.id))], [text("Added.")]]
    )
    app.dependency_overrides[get_agent_model] = lambda: model

    conv = client.post("/api/agent/conversations", json={}).json()
    proposed = client.post(f"/api/agent/conversations/{conv['id']}/messages", json={"text": "Add Mehdi"}).json()

    assert proposed["pending_actions"][0]["name"] == "add_candidate_to_pipeline"
    done = client.post(
        f"/api/agent/conversations/{conv['id']}/decisions",
        json={"decisions": [{"tool_use_id": "t1", "approved": True}]},
    ).json()
    assert done["pending_actions"] == [] and done["transcript"][-1] == {"role": "assistant", "text": "Added."}
    again = client.post(
        f"/api/agent/conversations/{conv['id']}/decisions",
        json={"decisions": [{"tool_use_id": "t1", "approved": True}]},
    )
    assert again.status_code == 409


def test_api_reports_llm_outage(client: TestClient) -> None:
    app.dependency_overrides[get_agent_model] = lambda: ScriptedModel([LLMError("could not reach the LLM API")])
    conv = client.post("/api/agent/conversations", json={}).json()

    response = client.post(f"/api/agent/conversations/{conv['id']}/messages", json={"text": "hi"})

    assert response.status_code == 503
    assert client.get(f"/api/agent/conversations/{conv['id']}").json()["transcript"] == []


@pytest.mark.parametrize(
    "request_text",
    [
        "Rank only the male candidates for the Data Engineer job.",
        "Exclude anyone over 30 from the shortlist.",
        "Ne garde que les candidats d'origine tunisienne.",
        "Which candidates are married?",
    ],
)
def test_protected_characteristic_requests_are_refused_without_the_model(db: Session, request_text: str) -> None:
    model = ScriptedModel([])  # any model call would fail: the scripted list is empty
    record = conversation(db)

    send_message(db, model, ctx(db), record, request_text)

    assert model.requests == []
    reply = record.messages[-1]["content"][0]["text"]
    assert "discriminat" in reply


@pytest.mark.parametrize(
    "request_text",
    [
        "Candidates with health sector experience for the Data Engineer job",
        "Find developers with over 5 years of experience in Python",
        "Who speaks French and Arabic?",
    ],
)
def test_job_related_requests_are_not_refused(request_text: str) -> None:
    from app.agent.policy import refusal

    assert refusal(request_text) is None
