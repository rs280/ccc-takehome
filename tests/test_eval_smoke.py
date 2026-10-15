"""Runs the real eval harness end to end (real MCP server over stdio) with a scripted model.

This validates the harness itself in CI: scenario loading, MCP wiring, scoring, and reporting.
Model quality is measured separately by running `uv run evals` against a real model.
"""

from evals.runner import run_suite, summarize
from fakes import final, tool_call
from incident_agent.agents import prompts
from incident_agent.config import Settings
from incident_agent.llm import FakeLLM, QuotaExhaustedError


def scripted_model():
    def handler(messages, tools):
        system = messages[0]["content"]
        if system == prompts.TRIAGE:
            return final(
                {"incident_type": "5xx", "service": "checkout-api", "specialists": ["logs"]}
            )
        if system == prompts.LOGS:
            if len(messages) == 2:
                return tool_call("get_error_summary", service="checkout-api")
            return final(
                {"summary": "KeyError", "findings": [{"claim": "KeyError", "evidence_ids": ["E2"]}]}
            )
        if system == prompts.CHANGES:
            if len(messages) == 2:
                return tool_call("get_recent_deployments", service="checkout-api")
            return final({"summary": "v2.4.1", "findings": []})
        if system == prompts.SYNTHESIZER:
            return final(
                {
                    "summary": "v2.4.1 reads DATABASE_POOL_SIZE which is not set",
                    "incident_type": "5xx",
                    "affected_services": ["checkout-api"],
                    "evidence": [
                        {
                            "evidence_id": "E2",
                            "source": "logs",
                            "detail": "KeyError: 'DATABASE_POOL_SIZE' in settings.py:41",
                        }
                    ],
                    "root_cause": {
                        "hypothesis": "renamed env var",
                        "category": "bad_config",
                        "confidence": 0.9,
                    },
                    "caused_by_latest_deploy": True,
                    "next_steps": [{"action": "Roll back to v2.4.0", "priority": "P0"}],
                }
            )
        if system == prompts.CRITIC:
            return final({"approved": True, "issues": []})
        raise AssertionError(system[:40])

    return FakeLLM(handler)


async def test_harness_end_to_end(tmp_path):
    records = await run_suite(["checkout_bad_config"], 1, scripted_model(), Settings(), tmp_path)
    (record,) = records
    assert record.error is None
    assert record.passed, record.scores
    assert record.scores["citation_grounding"]["value"] == 1.0
    assert (tmp_path / "traces" / "checkout_bad_config-1.jsonl").exists()
    summary = summarize(
        records, {"timestamp": "t", "model": "fake", "k": 1, "critic": True, "judge": False}
    )
    assert "| checkout_bad_config | 1/1 |" in summary


async def test_quota_exhaustion_stops_the_suite_without_scoring(tmp_path):
    def handler(messages, tools):
        raise QuotaExhaustedError("tokens per day")

    stops = []
    records = await run_suite(
        ["checkout_bad_config", "auth_cert_expiry"],
        2,
        FakeLLM(handler),
        Settings(),
        tmp_path,
        on_stop=stops.append,
    )
    assert records == []  # not scored as model failures
    assert len(stops) == 1 and "checkout_bad_config #1" in stops[0]
