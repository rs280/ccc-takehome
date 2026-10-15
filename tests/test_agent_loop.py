import pytest
from pydantic import BaseModel

from fakes import StubToolBox, final, tool_call
from incident_agent.agents.base import AgentOutputError, AgentSpec, run_agent
from incident_agent.evidence import EvidenceLedger
from incident_agent.llm import FakeLLM, LLMResponse, ToolCall
from incident_agent.tracing import Tracer


class Out(BaseModel):
    answer: str


SPEC = AgentSpec(
    name="tester",
    system_prompt="You test.",
    output_model=Out,
    tools=("search_logs",),
    max_tool_rounds=3,
)


def sequence(*responses):
    """FakeLLM handler that returns the given responses in order."""
    it = iter(responses)
    return FakeLLM(lambda messages, tools: next(it))


async def run(llm, toolbox=None, spec=SPEC, ledger=None):
    ledger = ledger if ledger is not None else EvidenceLedger()
    out = await run_agent(
        spec,
        "go",
        llm=llm,
        toolbox=toolbox or StubToolBox({"search_logs": "line A"}),
        ledger=ledger,
        tracer=Tracer(runs_dir=None),
    )
    return out, ledger


async def test_tool_result_recorded_with_evidence_id_and_shown_to_model():
    llm = sequence(tool_call("search_logs", service="x"), final({"answer": "done"}))
    out, ledger = await run(llm)
    assert out == Out(answer="done")
    assert ledger.get("E1").output == "line A"
    tool_msg = llm.calls[1][-1]
    assert tool_msg["role"] == "tool" and tool_msg["content"].startswith("[E1]")


async def test_disallowed_tool_is_refused_not_executed():
    toolbox = StubToolBox({"search_logs": "x", "get_metrics": "secret"})
    llm = sequence(tool_call("get_metrics", service="x"), final({"answer": "ok"}))
    out, ledger = await run(llm, toolbox)
    assert toolbox.calls == []
    assert "not available" in llm.calls[1][-1]["content"]
    assert len(ledger) == 0


async def test_bad_tool_arguments_reported_back():
    bad = LLMResponse(tool_calls=[ToolCall("c1", "search_logs", {}, argument_error="bad json")])
    llm = sequence(bad, final({"answer": "ok"}))
    toolbox = StubToolBox({"search_logs": "x"})
    await run(llm, toolbox)
    assert toolbox.calls == []
    assert "bad json" in llm.calls[1][-1]["content"]


async def test_tool_exception_becomes_error_evidence():
    toolbox = StubToolBox({"search_logs": RuntimeError("boom")})
    llm = sequence(tool_call("search_logs"), final({"answer": "ok"}))
    _, ledger = await run(llm, toolbox)
    assert ledger.get("E1").is_error and "boom" in ledger.get("E1").output


async def test_iteration_cap_forces_final_answer_without_tools():
    seen_tools = []

    def handler(messages, tools):
        seen_tools.append(tools)
        if tools:
            return tool_call("search_logs", query=str(len(messages)))
        return final({"answer": "forced"})

    out, ledger = await run(FakeLLM(handler))
    assert out.answer == "forced"
    assert len(ledger) == 3  # max_tool_rounds
    assert seen_tools[-1] is None


async def test_invalid_output_gets_one_repair_round():
    llm = sequence(LLMResponse(content="I think the answer is done"), final({"answer": "fixed"}))
    out, _ = await run(llm)
    assert out.answer == "fixed"
    assert "not valid" in llm.calls[1][-1]["content"]


async def test_gives_up_after_failed_repair():
    llm = sequence(LLMResponse(content="nope"), LLMResponse(content='{"wrong": 1}'))
    with pytest.raises(AgentOutputError):
        await run(llm)


async def test_duplicate_tool_call_reuses_evidence_id():
    llm = sequence(
        tool_call("search_logs", service="x"),
        tool_call("search_logs", service="x"),
        final({"answer": "ok"}),
    )
    toolbox = StubToolBox({"search_logs": "x"})
    _, ledger = await run(llm, toolbox)
    assert len(ledger) == 1 and len(toolbox.calls) == 1
    assert "already" in llm.calls[2][-1]["content"]
