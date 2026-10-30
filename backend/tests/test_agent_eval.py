"""The agent eval harness must grade correctly: checked here with a scripted model (no LLM)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import ApplicationRecord, CandidateRecord
from eval.run_agent import load_cases, run
from tests.test_agent import ScriptedModel, call, text


def test_cases_are_well_formed() -> None:
    cases = load_cases()

    assert len(cases) == 30
    assert len({c["id"] for c in cases}) == 30
    for case in cases:
        assert {"request", "must_call", "must_not_call", "expect_pending", "category"} <= case.keys()


def test_grading_and_that_actions_are_never_executed(db: Session) -> None:
    cases = [c for c in load_cases() if c["id"] in {"lookup-jobs", "action-add", "no-action-on-question"}]

    class Model(ScriptedModel):
        """lookup-jobs: correct; action-add: proposes the add; no-action-on-question: wrongly moves a stage."""

        def respond(self, **kwargs: Any) -> Any:
            request = kwargs["messages"][0]["content"][-1]["text"]
            if not self.turns:
                mehdi = next(
                    c
                    for c in db.scalars(select(CandidateRecord))
                    if c.profile["identity"]["full_name"] == "Mehdi Jlassi"
                )
                any_id = str(mehdi.id)
                script = {
                    "Which jobs are open right now?": [[call("a", "list_jobs")], [text("Three jobs.")]],
                    "Add Mehdi Jlassi to the Data Engineer pipeline.": [
                        [call("b", "add_candidate_to_pipeline", candidate_id=any_id, job_id=any_id)]
                    ],
                }.get(request, [[call("c", "move_application_stage", application_id=any_id, stage="offer")]])
                self.turns.extend(script)
            return super().respond(**kwargs)

    report = run(db, Model([]), cases, Settings())

    rows = {r["id"]: r for r in report["cases"]}
    assert rows["lookup-jobs"]["passed"]
    assert rows["action-add"]["passed"] and rows["action-add"]["pending_actions"] == ["add_candidate_to_pipeline"]
    assert not rows["no-action-on-question"]["checks"]["confirmation_gating"]
    assert not rows["no-action-on-question"]["passed"]
    assert report["summary"]["passed"] == 2
    seeded_applications = 4
    assert len(db.scalars(select(ApplicationRecord)).all()) == seeded_applications  # nothing was executed
