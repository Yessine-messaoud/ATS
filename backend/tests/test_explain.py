from typing import Any

from app.extraction import LLMError
from app.matching import MatchResult
from app.matching.explain import explain, template_explanation
from tests.conftest import FakeLLM
from tests.test_matching import CANDIDATE, run, with_


def weak_result() -> MatchResult:
    """A match with a missing required skill (Spark) and an unknown language level."""
    candidate = with_(
        CANDIDATE,
        skills=[{"name": "Python"}, {"name": "PostgreSQL"}],
        experiences=[{**CANDIDATE["experiences"][0], "responsibilities": ["Pipelines in Python on PostgreSQL"]}],
        languages=[{"language": "English"}],
    )
    result: MatchResult = run(candidate)
    return result


def draft(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "Solid Python and SQL profile; Spark is missing.",
        "strengths": [{"text": "Strong Python experience", "factor_ids": ["skill:python"]}],
        "gaps": [{"text": "No Spark experience", "factor_ids": ["skill:apache spark"]}],
        "interview_questions": [
            {"question": "How would you approach learning Spark?", "factor_ids": ["skill:apache spark"]}
        ],
    }
    return {**base, **overrides}


def test_template_cites_only_existing_factors() -> None:
    result = weak_result()
    explanation = template_explanation(result)
    factors = result.factors()

    assert explanation.source == "template"
    assert "Spark" in explanation.summary
    cited = [i for claim in explanation.strengths + explanation.gaps for i in claim.factor_ids]
    cited += [i for q in explanation.interview_questions for i in q.factor_ids]
    assert cited and all(i in factors for i in cited)
    assert any("English" in q.question for q in explanation.interview_questions)


def test_faithful_llm_explanation_is_kept() -> None:
    explanation = explain(weak_result(), FakeLLM([draft()]))

    assert explanation.source == "llm"
    assert explanation.dropped_claims == []
    assert explanation.gaps[0].text == "No Spark experience"


def test_unfaithful_claims_are_dropped() -> None:
    llm = FakeLLM(
        [
            draft(
                strengths=[
                    {"text": "Strong Python experience", "factor_ids": ["skill:python"]},
                    {"text": "Expert in Spark", "factor_ids": ["skill:apache spark"]},  # wrong polarity
                    {"text": "Great leadership", "factor_ids": ["leadership"]},  # unknown factor
                    {"text": "Python for 12 years", "factor_ids": ["skill:python"]},  # invented number
                ]
            )
        ]
    )

    explanation = explain(weak_result(), llm)

    assert [c.text for c in explanation.strengths] == ["Strong Python experience"]
    assert len(explanation.dropped_claims) == 3


def test_summary_with_invented_numbers_is_replaced() -> None:
    result = weak_result()

    explanation = explain(result, FakeLLM([draft(summary="Scores 99/100 with 15 years of Spark.")]))

    assert explanation.summary == template_explanation(result).summary
    assert any("summary" in reason for reason in explanation.dropped_claims)


def test_llm_failure_falls_back_to_template() -> None:
    class DownLLM(FakeLLM):
        def session(self, **_: object) -> Any:
            raise LLMError("unreachable")

    assert explain(weak_result(), DownLLM([])).source == "template"
    assert explain(weak_result(), FakeLLM([None, None])).source == "template"
    assert explain(weak_result(), None).source == "template"


def test_llm_receives_factors_but_no_personal_data() -> None:
    llm = FakeLLM([draft()])

    explain(weak_result(), llm)

    prompt = llm.sessions[0].prompts[0]
    assert "skill:python" in prompt
    assert CANDIDATE["identity"]["full_name"] not in prompt
    assert CANDIDATE["identity"]["email"] not in prompt
