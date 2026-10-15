"""End-to-end pipeline tests with a scripted model and an in-memory tool box."""

import json

import pytest

from fakes import StubToolBox, final, tool_call
from incident_agent.agents import prompts
from incident_agent.llm import FakeLLM, QuotaExhaustedError, RequestTooLargeError
from incident_agent.orchestrator import InvestigationError, investigate
from incident_agent.tracing import Tracer

CATALOG = json.dumps([{"name": "checkout-api", "depends_on": ["postgres"]}, {"name": "web"}])

REPORT = {
    "summary": "500s from missing env var",
    "incident_type": "5xx",
    "affected_services": ["checkout-api"],
    "evidence": [{"evidence_id": "E2", "source": "logs", "detail": "KeyError DATABASE_POOL_SIZE"}],
    "root_cause": {"hypothesis": "renamed env var", "category": "bad_config", "confidence": 0.9},
    "caused_by_latest_deploy": True,
    "next_steps": [{"action": "Roll back to v2.4.0", "priority": "P0"}],
}


def toolbox(metrics="{}"):
    return StubToolBox(
        {
            "list_services": CATALOG,
            "get_error_summary": '{"groups": [{"example": "KeyError: DATABASE_POOL_SIZE"}]}',
            "search_logs": "{}",
            "get_recent_deployments": '[{"id": "dep-1"}]',
            "get_deployment_diff": "{}",
            "get_metrics": metrics,
            "search_docs": "[]",
        }
    )


FIRST_TOOL = {
    prompts.LOGS: "get_error_summary",
    prompts.CHANGES: "get_recent_deployments",
    prompts.METRICS: "get_metrics",
    prompts.DOCS: "search_docs",
}


def scripted(report=REPORT, critic=None, fail_agent=None, triage=None):
    """Routes on the system prompt: each agent gets a plausible scripted behaviour."""
    critic_replies = list(critic or [{"approved": True, "issues": []}])
    report_replies = report if isinstance(report, list) else [report]

    def handler(messages, tools):
        system = messages[0]["content"]
        if system == prompts.TRIAGE:
            return final(
                triage
                or {
                    "incident_type": "5xx",
                    "service": "checkout-api",
                    "specialists": ["logs", "metrics"],
                }
            )
        if system in FIRST_TOOL:
            if system == fail_agent:
                raise RuntimeError("model crashed")
            if len(messages) == 2:  # first turn: call a tool
                return tool_call(FIRST_TOOL[system], service="checkout-api")
            return final({"summary": "s", "findings": [{"claim": "c", "evidence_ids": ["E2"]}]})
        if system == prompts.SYNTHESIZER:
            return final(report_replies.pop(0) if len(report_replies) > 1 else report_replies[0])
        if system == prompts.CRITIC:
            return final(critic_replies.pop(0))
        raise AssertionError("unexpected agent")

    return FakeLLM(handler)


async def run(llm, tools=None, **kw):
    return await investigate(
        "checkout-api returns 500s",
        llm=llm,
        toolbox=tools or toolbox(),
        tracer=Tracer(runs_dir=None),
        **kw,
    )


async def test_happy_path():
    result = await run(scripted())
    assert result.report.root_cause.category == "bad_config"
    # logs and changes are always added even if triage skipped them
    assert set(result.specialist_reports) == {"logs", "metrics", "changes"}
    assert result.ledger.get("E1").tool == "list_services"
    assert not result.revised and result.critic_verdicts[0].approved


async def test_specialist_failure_degrades_gracefully():
    llm = scripted(fail_agent=prompts.METRICS)
    result = await run(llm)
    assert "metrics" in result.failed_specialists
    synth_input = next(c for c in llm.calls if c[0]["content"] == prompts.SYNTHESIZER)[1]["content"]
    assert "FAILED" in synth_input and "metrics" in synth_input


async def test_critic_rejection_triggers_one_revision():
    fixed = {**REPORT, "summary": "revised"}
    llm = scripted(
        report=[REPORT, fixed], critic=[{"approved": False, "issues": ["timeline wrong"]}]
    )
    result = await run(llm)
    assert result.revised and result.report.summary == "revised"
    revision_prompt = [c for c in llm.calls if c[0]["content"] == prompts.SYNTHESIZER][-1][1][
        "content"
    ]
    assert "timeline wrong" in revision_prompt


async def test_hallucinated_citation_is_caught_without_llm_critic():
    bad = {**REPORT, "evidence": [{"evidence_id": "E99", "source": "logs", "detail": "x"}]}
    result = await run(scripted(report=[bad, REPORT]))
    assert "E99" in result.critic_verdicts[0].issues[0]
    assert result.revised and result.critic_verdicts[-1].approved


async def test_triage_unknown_service_falls_back_to_name_in_report():
    llm = scripted(triage={"incident_type": "5xx", "service": "checkout", "specialists": []})
    result = await run(llm)
    assert result.triage.service == "checkout-api"


async def test_all_specialists_failing_raises():
    def handler(messages, tools):
        if messages[0]["content"] == prompts.TRIAGE:
            return final(
                {"incident_type": "5xx", "service": "checkout-api", "specialists": ["logs"]}
            )
        raise RuntimeError("down")

    with pytest.raises(InvestigationError):
        await run(FakeLLM(handler))


FLAT = json.dumps({"metric": "error_rate", "change": "no significant change in level"})
STEP = json.dumps({"metric": "error_rate", "change": {"at": "10:10", "median_after": 38.7}})


async def test_confidence_capped_when_no_metric_changed():
    result = await run(scripted(), tools=toolbox(metrics=FLAT))
    assert result.report.root_cause.confidence == 0.4


async def test_confidence_kept_when_a_metric_changed():
    result = await run(scripted(), tools=toolbox(metrics=STEP))
    assert result.report.root_cause.confidence == 0.9


async def test_confidence_kept_without_metrics_evidence():
    # Metrics specialist failed: absence of evidence is not evidence of a weak signal.
    llm = scripted(fail_agent=prompts.METRICS)
    result = await run(llm, tools=toolbox(metrics=FLAT))
    assert result.report.root_cause.confidence == 0.9


async def test_quota_exhaustion_in_a_specialist_aborts_instead_of_degrading():
    base = scripted()

    def handler(messages, tools):
        if messages[0]["content"] == prompts.METRICS:
            raise QuotaExhaustedError("tokens per day")
        return base.handler(messages, tools)

    with pytest.raises(QuotaExhaustedError):
        await run(FakeLLM(handler))


def test_brief_excerpts_stay_within_budget_and_prefer_cited_evidence():
    from incident_agent.evidence import EvidenceLedger
    from incident_agent.orchestrator import BRIEF_EXCERPT_BUDGET, _within_budget

    ledger = EvidenceLedger()
    for i in range(40):
        ledger.add("logs", "search_logs", {"q": i}, "x" * 2000)
    chosen, omitted = _within_budget(
        ledger, ["E30", "E31"] + [f"E{i}" for i in range(1, 41)], BRIEF_EXCERPT_BUDGET
    )
    assert chosen[:2] == ["E30", "E31"]
    assert len(chosen) * 800 <= BRIEF_EXCERPT_BUDGET and omitted
    assert set(chosen) | set(omitted) == {f"E{i}" for i in range(1, 41)}


def too_large_for(agent, when=lambda messages: True):
    """Raise RequestTooLargeError for `agent` while `when(messages)` holds."""
    base = scripted()

    def handler(messages, tools):
        if messages[0]["content"] == agent and when(messages):
            raise RequestTooLargeError("413 input tokens per minute")
        return base.handler(messages, tools)

    return FakeLLM(handler)


async def test_oversized_synthesis_brief_retries_without_raw_excerpts():
    llm = too_large_for(
        prompts.SYNTHESIZER, lambda m: "## Raw evidence excerpts\n[" in m[1]["content"]
    )
    result = await run(llm)
    assert result.report.root_cause.category == "bad_config"
    briefs = [c[1]["content"] for c in llm.calls if c[0]["content"] == prompts.SYNTHESIZER]
    assert "Excerpts omitted" in briefs[-1]


async def test_synthesis_too_large_even_when_compact_fails_cleanly():
    with pytest.raises(InvestigationError, match="too large"):
        await run(too_large_for(prompts.SYNTHESIZER))


async def test_oversized_critic_request_falls_back_to_citation_check():
    result = await run(too_large_for(prompts.CRITIC))
    assert result.critic_verdicts[0].approved and not result.revised
